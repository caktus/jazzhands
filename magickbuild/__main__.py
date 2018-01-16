import os, sys
import re
import time
import subprocess
from io import StringIO
from distutils.dir_util import copy_tree

lang_dir_names = {
    'js': 'js',
    'css': 'css',
    'less': 'less',
    'styl': 'stylus',
}


def main(argv):
    project_dir = None
    if len(argv) == 1 or argv[1].startswith('-'):
        # detect project dir
        for dirname in os.listdir('.'):
            has_settings = (
                os.path.exists(os.path.join(dirname, 'settings'))
                or os.path.exists(os.path.join(dirname, 'settings.py'))
            )
            if os.path.isdir(dirname) and has_settings:
                project_dir = dirname
        assert project_dir
    else:
        project_dir = argv[1]

    index_files = {}

    css_dir = None
    js_dir = None

    stylus_watch = {}
    js_watch = {}

    app_asset_dirs = {}

    # Look through all the Python paths for packages with static files in them

    def record_app_asset_dir(lang):
        dir_name = lang_dir_names[lang]
        app_js_index = os.path.join(root, 'static', dir_name, 'index.%s' % lang)
        app_js_dir = os.path.join(root, 'static', dir_name)
        app_name = os.path.split(root)[-1]
        if os.path.exists(app_js_index):
            print(app_name, lang, app_js_index)
            app_asset_dirs.setdefault(lang, [])
            app_asset_dirs[lang].append((app_name, app_js_dir))

    for path in sys.path:
        for root, dirs, files in os.walk(path):
            if ".tox" in root or 'node_modules' in root or ".git" in root:
                continue
            if os.path.relpath(root).split('/', 1)[0] == os.path.relpath(project_dir):
                continue
            if 'lib/python' not in root or 'site-packages' in root:
                record_app_asset_dir('js')
                record_app_asset_dir('styl')

    for root, dirs, files in os.walk(project_dir):
        if 'node_modules' in root:
            continue
        if 'index.js' in files and 'js' not in index_files:
            print('JavaScript', root)
            index_files['js'] = os.path.join(root, 'index.js')
        if 'index.styl' in files and 'styl' not in index_files:
            print('Stylus', root)
            index_files['styl'] = os.path.join(root, 'index.styl')
            stylus_dir = root
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
            
    def collect_app_asset_src(lang):
        for (app_name, app_asset_dir) in app_asset_dirs[lang]:
            os.makedirs(os.path.join(js_dir, app_name), exist_ok=True)
            dest_dir = os.path.join(os.path.dirname(index_files[lang]), app_name)
            copy_tree(app_asset_dir, dest_dir)
            print("copying", app_name, lang, app_asset_dir, '->', dest_dir)
    
    def build_stylus():
        print("Building Stylus")
        collect_app_asset_src('styl')
        in_file = open(index_files['styl'], 'r')
        out_file = open(os.path.join(css_dir, 'bundle.css'), 'w')
        subprocess.call(['stylus'], cwd=stylus_dir, stdin=in_file, stdout=out_file)

    def build_less():
        print("Building Less")
        collect_app_asset_src('less')
        subprocess.call(['lessc', index_files['less'], os.path.join(css_dir, 'bundle.css')])
    
    def build_js():
        print("Building JS")
        collect_app_asset_src('js')
        p = subprocess.Popen(['browserify', index_files['js'], '-o', os.path.join(js_dir, 'bundle.js')], stderr=subprocess.PIPE)
        out, err = p.communicate()

        if p.returncode > 0:
            if '--auto-npm' in argv:
                err = err.decode('ascii')
                m = re.search(r"Cannot find module '(.*)' from", err)
                if m:
                    missing_dep = m.groups()[0]
                    subprocess.run(['npm', 'install', '--save', missing_dep])
                    build_js()
            else:
                print(out)
                print('---')
                print(err)

    if index_files.get('styl') and index_files.get('less'):
        print("ERROR: I don't know how to combine Stylus and Less in a single build... yet!")
        return

    if index_files.get('styl') and css_dir:
        build_stylus()
    elif index_files.get('less') and css_dir:
        build_less()

    if index_files['js'] and js_dir:
        build_js()
    
    if '--run' in argv:
        subprocess.Popen(['python', 'manage.py', 'runserver', '0.0.0.0:8000'])

        while 1:
            changed = False
            for fn in stylus_watch:
                if fn.endswith('.styl'):
                    if stylus_watch[fn] < os.stat(fn).st_mtime:
                        changed = True
                        stylus_watch[fn] = os.stat(fn).st_mtime
            if changed:
                build_stylus()
            
            changed = False
            for fn in js_watch:
                if fn.endswith('.js'):
                    if js_watch[fn] < os.stat(fn).st_mtime:
                        if not fn.endswith('bundle.js'):
                            changed = True
                            js_watch[fn] = os.stat(fn).st_mtime
            if changed:
                build_js()


if __name__ == '__main__':
    main(sys.argv)