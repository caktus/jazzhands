import os, sys
import re
import time
import subprocess
from io import StringIO
from shutil import rmtree, copytree

lang_dir_names = {
    'js': 'js',
    'css': 'css',
    'less': 'less',
    'styl': 'stylus',
}

index_files = {}

css_dir = None
js_dir = None

stylus_watch = {}
js_watch = {}

app_asset_dirs = {}

def pull_app_assets(from_path, to_path, copy=False):
    # copytree(from_path, to_path)
    if os.path.islink(to_path):
        os.unlink(to_path)
    elif os.path.exists(to_path):
        rmtree(to_path)
    print("copy" if copy else "link", from_path, "->", to_path)
    if copy:
        copytree(from_path, to_path)
    else:    
        os.symlink(from_path, to_path)

def record_app_asset_dir(dirs, root, lang):
    dir_name = lang_dir_names[lang]
    app_js_index = os.path.join(root, 'static', dir_name, 'index.%s' % lang)
    app_js_dir = os.path.join(root, 'static', dir_name)
    app_name = os.path.split(root)[-1]
    if os.path.exists(app_js_index):
        dirs.setdefault(lang, [])
        dirs[lang].append((app_name, app_js_dir))

def _process_jsx(fp):
    if fp.endswith('.js'):
        args = ['./node_modules/.bin/babel', '--presets=react,es2015', fp, '-o', fp]
        p = subprocess.Popen(args, stderr=subprocess.PIPE)
        print("JSX processed", fp)

def process_jsx(root):
    if os.path.isdir(root):
        for root, dirs, files in os.walk(root):
            for fn in files:
                fp = os.path.join(root, fn)
                _process_jsx(fp)
    else:
        _process_jsx(root)

def collect_app_asset_src(dirs, lang):
    if lang not in dirs:
        print("No %s to collect" % (lang,))
        return
    for (app_name, app_asset_dir) in dirs[lang]:
        dest_dir = os.path.join(os.path.dirname(index_files[lang]), app_name)
        
        print("collecting assets", app_name, lang, app_asset_dir, '->', dest_dir)
        if lang == 'js':
            dest_dir = os.path.join("node_modules", app_name)
            for root, dirs, files in os.walk(app_asset_dir):
                for fn in files:
                    if fn.endswith('.js'):
                        js_watch[os.path.join(root, fn)] = os.stat(os.path.join(root, fn)).st_mtime

        pull_app_assets(app_asset_dir, dest_dir, copy=(lang == 'js'))

        if lang == 'js':
            process_jsx(dest_dir)

def build_stylus(dirs):
    print("Building Stylus")
    in_file = open(index_files['styl'], 'r')
    out_file = open(os.path.join(css_dir, 'bundle.css'), 'w')
    stylus_dir = os.path.dirname(index_files['styl'])
    stylus_bin = os.path.join(os.path.relpath(".", stylus_dir), "node_modules/.bin/stylus")
    subprocess.call([stylus_bin, '--resolve-url'], cwd=stylus_dir, stdin=in_file, stdout=out_file)

def build_less(dirs):
    print("Building Less")
    subprocess.call(['lessc', index_files['less'], os.path.join(css_dir, 'bundle.css')])

def build_js(dirs):
    print("Building JS")
    args = ['./node_modules/.bin/browserify']
    args.extend("-t [ babelify --presets [ react es2015 ] ]".split())
    args.extend([index_files['js'], '-o', os.path.join(js_dir, 'bundle.js')])
    p = subprocess.Popen(args, stderr=subprocess.PIPE)
    out, err = p.communicate()

    if p.returncode > 0:
        if '--auto-npm' in sys.argv:
            err = err.decode('ascii')
            m = re.search(r"Cannot find module '(.*)' from", err)
            if m:
                missing_dep = m.groups()[0]
                subprocess.run(['npm', 'install', '--save', missing_dep])
                build_js()
        else:
            print(out)
            print('---')
            print(err.decode('utf8'))

def main(argv):
    global js_dir
    global css_dir

    DO_COLLECT = False
    DO_BUILD = False
    DO_RUN = False

    ### INSPECT AND CONFIGURE

    if len(sys.argv) <= 1:
        DO_COLLECT = DO_BUILD = True
    elif sys.argv[1] == 'setup':
        # Do one time setup stuff for the project
        args = [
            "npm", "install", "--save",
            "babel-core",
            "babel-cli",
            "babelify",
            "babel-preset-react",
            "babel-preset-es2015",
        ]
        subprocess.call(args)
        return
    elif sys.argv[1] == 'build':
        DO_COLLECT = DO_BUILD = True
    elif sys.argv[1] == 'collect':
        DO_COLLECT = True
    elif sys.argv[1] == 'run':
        DO_COLLECT = DO_BUILD = DO_RUN = True

    project_dir = None
    for dirname in os.listdir('.'):
        has_settings = (
            os.path.exists(os.path.join(dirname, 'settings'))
            or os.path.exists(os.path.join(dirname, 'settings.py'))
        )
        if os.path.isdir(dirname) and has_settings:
            project_dir = dirname
    assert project_dir

    # Look through all the Python paths for packages with static files in them
    for path in sys.path:
        for root, dirs, files in os.walk(path):
            if ".tox" in root or 'node_modules' in root or ".git" in root:
                continue
            if os.path.relpath(root).split('/', 1)[0] == os.path.relpath(project_dir):
                continue
            if 'lib/python' not in root or 'site-packages' in root:
                record_app_asset_dir(app_asset_dirs, root, 'js')
                record_app_asset_dir(app_asset_dirs, root, 'styl')
                record_app_asset_dir(app_asset_dirs, root, 'less')

    # Find all the asset files in the project itself
    for root, dirs, files in os.walk(project_dir, followlinks=True):
        if 'node_modules' in root:
            continue
        if 'index.js' in files and 'js' not in index_files:
            print('JavaScript', root)
            index_files['js'] = os.path.join(root, 'index.js')
        if 'index.styl' in files and 'styl' not in index_files:
            print('Stylus', root)
            index_files['styl'] = os.path.join(root, 'index.styl')
        if 'index.less' in files and 'less' not in index_files:
            print('Less', root)
            index_files['less'] = os.path.join(root, 'index.less')
        if root.endswith('static/css'):
            print('CSS Destination', root)
            css_dir = root
        if root.endswith('static/js'):
            print('JS Destination', root)
            js_dir = root
        
        for fn in files:
            if fn.endswith('.styl'):
                fn = os.path.join(root, fn)
                stylus_watch[fn] = os.stat(fn).st_mtime
            if fn.endswith('.js'):
                fn = os.path.join(root, fn)
                js_watch[fn] = os.stat(fn).st_mtime

    if index_files.get('styl') and index_files.get('less'):
        print("ERROR: I don't know how to combine Stylus and Less in a single build... yet!")
        return

    ### COLLECT

    if DO_COLLECT:
        if index_files.get('styl') and css_dir:
            collect_app_asset_src(app_asset_dirs, 'styl')
        elif index_files.get('less') and css_dir:
            collect_app_asset_src(app_asset_dirs, 'less')

        if index_files['js'] and js_dir:
            jsx_registry_path = os.path.join(os.path.dirname(index_files['js']), 'jsx_registry.js')
            subprocess.call(['python', 'manage.py', 'compilejsx'], stdout=open(jsx_registry_path, 'w'))
            process_jsx(jsx_registry_path)
            
            collect_app_asset_src(app_asset_dirs, 'js')

    ### BUILD

    if DO_BUILD:
        if index_files.get('styl') and css_dir:
            build_stylus(app_asset_dirs)
        elif index_files.get('less') and css_dir:
            build_less(app_asset_dirs)

        if index_files['js'] and js_dir:
            build_js(app_asset_dirs)

    ### RUN
    
    if DO_RUN:
        subprocess.Popen(['python', 'manage.py', 'runserver', '0.0.0.0:8000'])

        while 1:
            changed = False
            for fn in stylus_watch:
                if fn.endswith('.styl'):
                    if stylus_watch[fn] < os.stat(fn).st_mtime:
                        changed = True
                        stylus_watch[fn] = os.stat(fn).st_mtime
            if changed:
                collect_app_asset_src(app_asset_dirs, 'styl')
                build_stylus(app_asset_dirs)
            
            changed = False
            for fn in js_watch:
                if fn.endswith('.js'):
                    if js_watch[fn] < os.stat(fn).st_mtime:
                        if not fn.endswith('bundle.js'):
                            changed = True
                            js_watch[fn] = os.stat(fn).st_mtime
            if changed:
                collect_app_asset_src(app_asset_dirs, 'js')
                build_js(app_asset_dirs)


if __name__ == '__main__':
    main(sys.argv)