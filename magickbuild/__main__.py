import os, sys
import time
import subprocess
from distutils.dir_util import copy_tree


def main(argv):
    project_dir = None
    if len(argv) == 1 or argv[1].startswith('-'):
        # detect project dir
        for dirname in os.listdir('.'):
            if os.path.isdir(dirname) and os.path.exists(os.path.join(dirname, 'settings')):
                project_dir = dirname
    else:
        project_dir = argv[1]

    index_files = {}

    css_dir = None
    js_dir = None

    stylus_watch = {}
    js_watch = {}

    app_js_dirs = []

    for path in sys.path:
        for root, dirs, files in os.walk(path):
            if ".tox" in root or 'node_modules' in root or ".git" in root:
                continue
            if os.path.relpath(root).split('/', 1)[0] == os.path.relpath(project_dir):
                continue
            if 'lib/python' not in root or 'site-packages' in root:
                app_js_index = os.path.join(root, 'static', 'js', 'index.js')
                app_js_dir = os.path.join(root, 'static', 'js')
                app_name = os.path.split(root)[-1]
                if os.path.exists(app_js_index):
                    print(app_name, app_js_index)
                    app_js_dirs.append((app_name, app_js_dir))

    for root, dirs, files in os.walk(project_dir):
        if 'node_modules' in root:
            continue
        if 'index.js' in files:
            print('JavaScript', root)
            index_files['js'] = os.path.join(root, 'index.js')
        if 'index.styl' in files:
            print('Stylus', root)
            index_files['styl'] = os.path.join(root, 'index.styl')
            stylus_dir = root
        if 'index.less' in files:
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
    
    def build_stylus():
        print("Building Stylus")
        in_file = open(index_files['styl'], 'r')
        out_file = open(os.path.join(css_dir, 'bundle.css'), 'w')
        subprocess.call(['stylus'], cwd=stylus_dir, stdin=in_file, stdout=out_file)

    def build_less():
        print("Building Less")
        subprocess.call(['lessc', index_files['less'], os.path.join(css_dir, 'bundle.css')])
    
    def build_js():
        print("Building JS")
        for (app_name, app_js_dir) in app_js_dirs:
            os.makedirs(os.path.join(js_dir, app_name), exist_ok=True)
            copy_tree(app_js_dir, os.path.join(js_dir, app_name))
        subprocess.call(['browserify', index_files['js'], '-o', os.path.join(js_dir, 'bundle.js')])

    if index_files.get('styl') and css_dir:
        build_stylus()
    elif index_files.get('less') and css_dir:
        build_less()

    if index_files['js'] and js_dir:
        build_js()
    
    if '--run' in argv:
        subprocess.Popen(['python', 'manage.py', 'runserver'])

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