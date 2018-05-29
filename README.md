# jazzhands

Jazz Hands is a automatic build and dev-run tool for Django projects with modern frontends.

![Caution: Jazz Hands!](jazzhands.gif)

* Detects and compiles ES6 to JS and Less or Stylus to CSS!
* Allows importing ES6, Less, and Stylus modules from Django apps!
* Builds your bundle.js and bundle.css files!
* Runs your dev server and automatically rebuilds front-end assets when change are detected!
* Is Magick :sparkles:!

## Installation

You can install Jazzhands locally in the virtual environment of a Django project.

```
pip install 'git+https://github.com/caktus/jazzhands@develop'
```

## Setup

Once installed
you can install prerequisite NPM packages for ECMAScript compilation with Jazzhand's `setup`
command.

The setup command needs to know what Babel presets and transform plugins you want. The setup will add the necessary entries to your `package.json` file as well as generate a `.babelrc` configuration file for you. You'll be given the `es2017` preset by default, which allows your Javascript modules to use all the ES2017 language features.

```
jazzhands setup
```

One or more presets are allowed with the `-p` option. For a React project you would add the `react` preset as well as the `es2017` preset.

```
jazzhands setup -p es2017 -p react
```

If you have specific language features you want to include, add them with the `-t` option. Multiple transforms can also be included.

```
jazzhands setup -p es2017 -t object-rest-spread
```

To learn more about presets and transforms you can read the Babel docs on plugins at `https://babeljs.io/docs/plugins/`.

## Collecting

To use Jazzhands to collect non-static frontend assets (things that get compiled or otherwise converted)
into your local project, run the `collect` command.

```jazzhands collect
```

Jazzhands will locate Python packages that contain a `static/` dirctory with either a `js/`, `less/`, or
`stylus/` folder within it. If any of those directories has an index file (`index.js`, etc.) then Jazzhands
will try to collect that directory as a Javascript package or a Less/Stylus library into your project.

Javascript will be collected into your `node_modules/` directory for import. Less and Stylus libraries will
be linked into your project's own `static/less/` or `static/stylus/`.

## Building

Jazzhands can also build your project's frontend assets for you. This includes compiling modern ECMAScript to
browser-compatible Javascript in a `bundle.js` file and converting both Less and Stylus in your project to
a combined `bundle.css` file.

Jazzhands will locate a top-level `index.js` file in your project and attempt to compile this into the JS
bundle. It will similarly locate `index.less` or `index.styl` and create a bundle at `static/css/bundle.css`.
If you have both Less and Stylus, they will be combined into a single bundle together.

The `build` command will run the `collect` command first, so the built bundles can include usage of Javascript
or styles that have been collected from Django apps or other Python libraries in your project. You can run
the build command directly.

```
jazzhands build
```

## Running

Finally, if you are using Jazzhands you're probably doing active work on your frontend in a local development
environment and Jazzhands can help with that! As well as collecting assets and building frontend bundles, it
can manage running your Django development server while watching for changes in any of your frontend assets,
even if they came from a 3rd party app in the collection stage.

Jazzhands doesn't have options to control the address or ports yet, so it will run the local development
server on port 8000 as a default. The `run` command executes the `collect` and `build` commands first, then
starts up Django's own `runserver` management command.

```
jazzhands run
```

While the development server is running, if changes are detected in any of the JS, Less, or Stylus files used
in the build process the bundles will be regenerated automatically. If a change is detected in files that came
from another package, they will be reimported into the project.

### Experimental Feature

#### ```--auto-npm```

Use the experimental feature (which may or may not be removed) called Auto NPM Install. When using this feature, if compiling the `bundle.js` file fails and that failure appears
to be caused by a missing NPM package, we will try to install it automatically and add
it to your `package.json`.

This lets you add an experiment with new code using anything available on the NPM registry.