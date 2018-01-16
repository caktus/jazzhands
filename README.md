# magickbuild

Magick Build is a automatic build and dev-run tool for modern Django projects.

* Detects and compiles ES6 to JS and Less or Stylus to CSS!
* Allows importing ES6, Less, and Stylus modules from Django apps!
* Builds your bundle.js and bundle.css files!
* Runs your dev server and automatically rebuilds front-end assets when change are detected!
* Is Magick :sparkles:!

```
pip install -e git@github.com:caktus/magickbuild.git
python -m magickbuild project_folder/ # build
python -m magickbuild project_folder/ --run # build, run dev server, rebuild on changes
```

