from __future__ import print_function

import os
import re
from shutil import rmtree, copytree
import subprocess
import sys
import time
import json
from warnings import warn

import argparse


lang_dir_names = {
    'js': 'js',
    'css': 'css',
    'less': 'less',
    'styl': 'stylus',
}

index_files = {}

css_dir = None
js_dir = None

watch = {
    'js': {},
    'less': {},
    'styl': {},
}

app_asset_dirs = {}

manage_dir = None
project_dir = None


def pull_app_assets(from_path, to_path, copy=False):
    """Copy or symlink an asset directory from one location to another."""

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
    """For a given app located at `root`, add an entry for a language's
    assets if there is a top-level index file matching it.

    For example, if a Django app has an index.js in the expected location,
    record it as the location of that application's javascript to be
    collected later.
    """

    dir_name = lang_dir_names[lang]
    app_js_index = os.path.join(root, 'static', dir_name, 'index.%s' % lang)
    app_js_dir = os.path.join(root, 'static', dir_name)
    app_name = os.path.split(root)[-1]
    if os.path.exists(app_js_index):
        dirs.setdefault(lang, [])
        dirs[lang].append((app_name, app_js_dir))


def _process_jsx(fp):
    """Utility to transpile ES6 to browser-friendly JS."""

    if fp.endswith('.js'):
        babel_bin = './node_modules/.bin/babel'
        # args '--presets=react,es2015',
        args = [babel_bin, fp, '-o', fp]
        if not os.path.exists(babel_bin):
            print("ERROR: Javascript found, but babel is not installed.")
            print("To fix, install babel in this project:")
            print("    jazzhands setup")
            print("This will update your package.json, so look at the changes and commit them appropriately.")
            sys.exit(1)
        subprocess.call(args, stderr=subprocess.PIPE)
        print("JSX processed", fp)


def process_jsx(root):
    """Utility to translate all located files in a directory from ES6 to JS."""

    if os.path.isdir(root):
        for root, dirs, files in os.walk(root):
            for fn in files:
                fp = os.path.join(root, fn)
                _process_jsx(fp)
    else:
        _process_jsx(root)


def collect_app_asset_src(dirs, lang):
    """Collects (copy or symlink) assets from apps into the project.

    JavaScript "packages" are placed in node_modules/ to be imported. Less and
    Stylus packages are placed adjacent to the projects own index.less or
    index.styl for relative importing.

    If the file is Javascript it is also processed for any necessary JSX/ES
    transpiling after being installed in node_modules/
    """

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
                        watch['js'][os.path.join(root, fn)] = os.stat(os.path.join(root, fn)).st_mtime

        pull_app_assets(app_asset_dir, dest_dir, copy=(lang == 'js'))

        if lang == 'js':
            process_jsx(dest_dir)


def new_css_bundle():
    bundle_css_path = os.path.join(css_dir, 'bundle.css')
    if os.path.exists(bundle_css_path):
        os.unlink(bundle_css_path)
    return bundle_css_path


def build_stylus(dirs):
    print("Building Stylus")
    in_file = open(index_files['styl'], 'r')
    out_file = open(os.path.join(css_dir, 'bundle.css'), 'a')
    stylus_dir = os.path.dirname(index_files['styl'])
    stylus_bin = os.path.abspath("node_modules/.bin/stylus")
    if not os.path.exists(stylus_bin):
        print("ERROR: Stylus files found, but stylus is not installed.")
        print("To fix, install stylus in this project using NPM:")
        print("    npm install --save stylus")
        print("Or, using Yarn:")
        print("    yarn add stylus")
        sys.exit(1)
    subprocess.call([stylus_bin, '--resolve-url'], cwd=stylus_dir, stdin=in_file, stdout=out_file)


def build_less(dirs):
    print("Building Less")
    subprocess.call(['lessc', index_files['less'], os.path.join(css_dir, 'bundle.css')])


def build_js(dirs):
    print("Building JS")
    args = ['./node_modules/.bin/browserify']
    args.extend("-t [ babelify ]".split())
    args.extend([index_files['js'], '-o', os.path.join(js_dir, 'bundle.js')])
    print(args)
    proc = subprocess.Popen(args, stderr=subprocess.PIPE)
    out, err = proc.communicate()

    if proc.returncode > 0:
        # Experimental "auto install" feature for missing NPM dependencies during development
        if args.auto_npm:
            warn("--auto-npm is an experimental feature and maybe a bad idea. It might go away soon.")
            err = err.decode('ascii')
            match = re.search(r"Cannot find module '(.*)' from", err)
            if match:
                missing_dep = match.groups()[0]
                subprocess.call(['npm', 'install', '--save', missing_dep])
                build_js()
        else:
            print(out)
            print('---')
            print(err.decode('utf8'))


def manage_py(args, background=False):
    cwd = os.getcwd()
    os.chdir(manage_dir)
    try:
        if background:
            return subprocess.Popen(['python', 'manage.py'] + args)
        else:
            return subprocess.call(['python', 'manage.py'] + args)
    finally:
        os.chdir(cwd)


def main(argv=sys.argv):
    global js_dir
    global css_dir
    global project_dir
    global manage_dir
    global args

    DO_COLLECT = False
    DO_BUILD = False
    DO_RUN = False

    # INSPECT AND CONFIGURE
    # Based on commmand line arguments enable steps in order or
    # collect, build, run or the setup command.
    # build implies collect, run implies build and collect. setup runs on its own.

    parser = argparse.ArgumentParser()
    parser.set_defaults(which=None)
    # parser.add_argument('command', type=str, action='store')
    subparsers = parser.add_subparsers()
    parsers = {}
    def add_command(cmd):
        parsers[cmd] = subparsers.add_parser(cmd)
        parsers[cmd].set_defaults(which=cmd)

    add_command('setup')
    parsers['setup'].add_argument('-p', '--preset', action='append', type=str, default=[])
    parsers['setup'].add_argument('-t', '--transform', action='append', type=str, default=[])

    add_command('collect')

    add_command('build')

    add_command('run')
    parsers['run'].add_argument('--auto-npm', action='store_true')

    args = parser.parse_args()

    if not args.which:
        DO_COLLECT = DO_BUILD = True
    elif args.which == 'setup':
        # Do one time setup stuff for the project
        # Currently defaults to Babel's ES2017
        cargs = [
            "npm", "install", "--save",
            "babel-core",
            "babel-cli",
            "babelify",
        ]

        # Default presets, if none are given
        if not args.preset:
            args.preset = ["es2017"]

        # Build list of packages to install for requested presets and transforms
        for preset in args.preset:
            cargs.append("babel-preset-" + preset)
        for transform in args.transform:
            cargs.append("babel-plugin-transform-" + transform)

        babelrc = {
            "presets": args.preset,
            "plugins": ["transform-" + t for t in args.transform],
        }
        if os.path.exists(".babelrc"):
            print("Refusing to overwrite existing .babelrc file. Please update it manually.")
            sys.exit(1)
        json.dump(babelrc, open(".babelrc", "w"))
        
        subprocess.call(cargs)
        return
    elif args.which == 'build':
        DO_COLLECT = DO_BUILD = True
    elif args.which == 'collect':
        DO_COLLECT = True
    elif args.which == 'run':
        DO_COLLECT = DO_BUILD = DO_RUN = True

    # Locate the "main" Python package for the project in the current directory.
    project_dir = None
    for dirname in os.listdir('.'):
        has_settings = (
            os.path.exists(os.path.join(dirname, 'settings'))
            or os.path.exists(os.path.join(dirname, 'settings.py'))
        )
        if os.path.isdir(dirname) and has_settings:
            project_dir = dirname
        if os.path.exists(os.path.join(dirname, 'manage.py')):
            manage_dir = dirname
    if not manage_dir:
        manage_dir = os.path.abspath(".")
    
    # If we can't find the location of the project's "main" package, abort
    if not project_dir:
        print("Could not locate your project's main package. Jazzhands tries to locate this relative"
            " to a `settings` package or `settings.py` module.")
        sys.exit(1)

    # Look through all the Python paths for packages with static files in them
    exclude_dirs = ('.tox', 'node_modules', '.git')
    for path in sys.path:
        for root, dirs, files in os.walk(path):
            # Skip some obvious irrelevant directories
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            # Skip Python packages / Django apps built into the project itself
            if os.path.relpath(root).split('/', 1)[0] == os.path.relpath(project_dir):
                continue
            # Try to find pip-installed packages to collect assets from and record the locations
            # of found assets for later collection.
            if 'lib/python' not in root or 'site-packages' in root:
                record_app_asset_dir(app_asset_dirs, root, 'js')
                record_app_asset_dir(app_asset_dirs, root, 'styl')
                record_app_asset_dir(app_asset_dirs, root, 'less')

    # Find all the asset files in the project itself
    # including the destination locations `js_dir` and `css_dir`
    for root, dirs, files in os.walk(project_dir, followlinks=True):
        # Skip NPM installed packages that browserify can already find
        if 'node_modules' in root:
            continue

        # Find top-level JS/Less/Stylus locations in the project
        if 'index.js' in files and 'js' not in index_files:
            print('JavaScript', root)
            index_files['js'] = os.path.join(root, 'index.js')
            js_dir = root
        if 'index.styl' in files and 'styl' not in index_files:
            print('Stylus', root)
            index_files['styl'] = os.path.join(root, 'index.styl')
        if 'index.less' in files and 'less' not in index_files:
            print('Less', root)
            index_files['less'] = os.path.join(root, 'index.less')

        # Find CSS static locations for generated bundles to live, separate from Less/Stylus source
        # The JS location is identified above, because index.js and bundle.js are together
        if root.endswith('static/css'):
            print('CSS Destination', root)
            css_dir = root

        # Register all the appropriate files to the watch list
        for fn in files:
            for ext in ('js', 'styl', 'less'):
                if fn.endswith('.' + ext):
                    fn = os.path.join(root, fn)
                    watch[ext][fn] = os.stat(fn).st_mtime
                    break

    # COLLECT

    if DO_COLLECT:
        if index_files.get('styl') and css_dir:
            collect_app_asset_src(app_asset_dirs, 'styl')
        if index_files.get('less') and css_dir:
            collect_app_asset_src(app_asset_dirs, 'less')

        if index_files['js'] and js_dir:
            jsx_registry_path = os.path.join(os.path.dirname(index_files['js']), 'jsx_registry.js')
            try:
                import django_jsx  # noqa: F401
            except ImportError:
                pass
            else:
                manage_py(['compilejsx', '-o', jsx_registry_path])
                process_jsx(jsx_registry_path)
            collect_app_asset_src(app_asset_dirs, 'js')

    # BUILD

    if DO_BUILD:

        # Build a bundle from the LESS, if present, then append the Stylus bundle, if present.
        if css_dir:
            bundle_css_path = new_css_bundle()
            if index_files.get('less'):
                build_less(app_asset_dirs)
            if index_files.get('styl'):
                build_stylus(app_asset_dirs)
        elif index_files.get('less') or index_files.get('styl'):
            print("Found Less or Stylus files, but no obvious location to generate bundle.css")
            print("(expected to find a .../static/css/ somewhere in the project)")
            sys.exit(1)

        if index_files['js'] and js_dir:
            build_js(app_asset_dirs)

    # RUN

    if DO_RUN:
        manage_py(['runserver', '0.0.0.0:8000'], background=True)

        while 1:
            time.sleep(1)

            # Less and Stylus could be combined, so when we watch we watch them
            # together and clear the current bundle if we rebuild either. Otherwise,
            # they'll keep being appended.

            stylus_changed = False
            for fn in watch['styl']:
                if fn.endswith('.styl'):
                    if watch['styl'][fn] < os.stat(fn).st_mtime:
                        stylus_changed = True
                        watch['styl'][fn] = os.stat(fn).st_mtime

            less_changed = False
            for fn in watch['less']:
                if fn.endswith('.less'):
                    if watch['less'][fn] < os.stat(fn).st_mtime:
                        less_changed = True
                        watch['less'][fn] = os.stat(fn).st_mtime

            if less_changed or stylus_changed:
                new_css_bundle()

                if watch['styl']:
                    collect_app_asset_src(app_asset_dirs, 'styl')
                    build_stylus(app_asset_dirs)
            
                if watch['less']:
                    collect_app_asset_src(app_asset_dirs, 'less')
                    build_less(app_asset_dirs)

            changed = False
            for fn in watch['js']:
                if fn.endswith('.js'):
                    if watch['js'][fn] < os.stat(fn).st_mtime:
                        if not fn.endswith('bundle.js'):
                            changed = True
                            watch['js'][fn] = os.stat(fn).st_mtime
            if changed:
                collect_app_asset_src(app_asset_dirs, 'js')
                build_js(app_asset_dirs)


if __name__ == '__main__':
    main(sys.argv)