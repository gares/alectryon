# -*- makefile -*-
### Auto-generated with etc/regen_makefile.py ###
### Do not edit! ###

_output/tests/:
	mkdir -p $@

# HTML4
_output/tests/dialects.4.html: tests/dialects.rst
	$(alectryon) --html-dialect=html4 -o $@ $<
# HTML5
_output/tests/dialects.5.html: tests/dialects.rst
	$(alectryon) --html-dialect=html5 -o $@ $<
# LaTeX
_output/tests/dialects.tex: tests/dialects.rst
	$(alectryon) --latex-dialect=pdflatex -o $@ $<
# XeLaTeX
_output/tests/dialects.xe.tex: tests/dialects.rst
	$(alectryon) --latex-dialect=xelatex -o $@ $<
# LuaLaTeX
_output/tests/dialects.lua.tex: tests/dialects.rst
	$(alectryon) --latex-dialect=lualatex -o $@ $<

# reST → Coq
_output/tests/directive-options.html: tests/directive-options.rst
	$(alectryon) $<
# reST → LaTeX
_output/tests/directive-options.xe.tex: tests/directive-options.rst
	$(alectryon) $< --latex-dialect xelatex -o $@

# Run doctests
_output/tests/doctests.out: tests/doctests.py | _output/tests/
	$(PYTHON) $< | sed 's/\(tests\) in [0-9.]\+s$$/\1/g' > $@

# Coq+reST → LaTeX
_output/tests/latex_formatting.tex: tests/latex_formatting.v
	$(alectryon) $< --backend latex

# Coq+reST → JSON
_output/tests/linter.lint.json: tests/linter.v
	$(alectryon) $< --backend lint

# Coq → JSON
_output/tests/recording.v.io.json: tests/recording.v
	$(alectryon) $< --frontend coq --backend json

# IO → HTML
_output/tests/recording.v.html: tests/recording.v.io.json
	$(alectryon) $<
# IO → HTML
_output/tests/recording.snippets.html: tests/recording.v.io.json
	$(alectryon) $< --backend snippets-html
# IO → LaTeX
_output/tests/recording.snippets.tex: tests/recording.v.io.json
	$(alectryon) $< --backend snippets-latex

# Coq → HTML
_output/tests/screenshot.html: tests/screenshot.v
	$(alectryon) $<

_output/tests/dialects.4.html _output/tests/dialects.5.html _output/tests/dialects.tex _output/tests/dialects.xe.tex _output/tests/dialects.lua.tex _output/tests/directive-options.html _output/tests/directive-options.xe.tex _output/tests/doctests.out _output/tests/latex_formatting.tex _output/tests/linter.lint.json _output/tests/recording.v.io.json _output/tests/recording.v.html _output/tests/recording.snippets.html _output/tests/recording.snippets.tex _output/tests/screenshot.html: out_dir := _output/tests

targets += _output/tests/dialects.4.html _output/tests/dialects.5.html _output/tests/dialects.tex _output/tests/dialects.xe.tex _output/tests/dialects.lua.tex _output/tests/directive-options.html _output/tests/directive-options.xe.tex _output/tests/doctests.out _output/tests/latex_formatting.tex _output/tests/linter.lint.json _output/tests/recording.v.io.json _output/tests/recording.v.html _output/tests/recording.snippets.html _output/tests/recording.snippets.tex _output/tests/screenshot.html
