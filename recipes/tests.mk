# -*- makefile -*-
### Auto-generated with etc/regen_makefile.py ###
### Do not edit! ###

_output/tests/:
	mkdir -p $@

# Coq → HTML
_output/tests/corner_cases.html: tests/corner_cases.rst
	$(alectryon) --stdin-filename $< --frontend rst -o $@ - < $<
# Coq → LaTeX
_output/tests/corner_cases.xe.tex: tests/corner_cases.rst
	$(alectryon) $< -o $@ --latex-dialect xelatex

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

# reST → HTML
_output/tests/display-flags.html: tests/display-flags.rst
	$(alectryon) $<

# Run doctests
_output/tests/doctests.out: tests/doctests.py | _output/tests/
	$(PYTHON) $< | sed 's/\(tests\) in [0-9.]\+s$$/\1/g' > $@

# reST → JSON errors
_output/tests/errors.lint.json: tests/errors.rst
	$(alectryon) $< --backend lint; echo "exit: $$?" >> $@
# reST → HTML + errors
_output/tests/errors.txt: tests/errors.rst
	$(alectryon) $< --copy-assets none --backend webpage -o /dev/null 2> $@; echo "exit: $$?" >> $@

# Coq+reST → LaTeX
_output/tests/latex_formatting.tex: tests/latex_formatting.v
	$(alectryon) $< --backend latex

# reST → Coq
_output/tests/literate.v: tests/literate.rst
	$(alectryon) $< --backend coq

# Coq → reST
_output/tests/literate.v.rst: tests/literate.v
	$(alectryon) $< --backend rst --mark-point 522 ⊙

# Coq → HTML
_output/tests/screenshot.html: tests/screenshot.v
	$(alectryon) $<

# reST → HTML
_output/tests/stylesheets.html: tests/stylesheets.v
	DOCUTILSCONFIG=tests/stylesheets.docutils.conf \
       $(alectryon) $< --pygments-style emacs --backend webpage -o - | sed -r '/^ *<style type="text.css">/,/^ *<.style>/ { /^ *<style |<.style>|Alectryon/b; d}' > $@
# reST → LaTeX
_output/tests/stylesheets.part.tex: tests/stylesheets.v
	DOCUTILSCONFIG=tests/stylesheets.docutils.conf \
       $(alectryon) $< --pygments-style emacs --backend latex -o - | sed -r '/^% embedded stylesheet/,/^\\makeatother/ { /^\\makeat|Alectryon/b; d}' > $@

# Coq → HTML
_output/tests/syntax_highlighting.html: tests/syntax_highlighting.v
	$(alectryon) $<

_output/tests/corner_cases.html _output/tests/corner_cases.xe.tex _output/tests/dialects.4.html _output/tests/dialects.5.html _output/tests/dialects.tex _output/tests/dialects.xe.tex _output/tests/dialects.lua.tex _output/tests/directive-options.html _output/tests/directive-options.xe.tex _output/tests/display-flags.html _output/tests/doctests.out _output/tests/errors.lint.json _output/tests/errors.txt _output/tests/latex_formatting.tex _output/tests/literate.v _output/tests/literate.v.rst _output/tests/screenshot.html _output/tests/stylesheets.html _output/tests/stylesheets.part.tex _output/tests/syntax_highlighting.html: out_dir := _output/tests

targets += _output/tests/corner_cases.html _output/tests/corner_cases.xe.tex _output/tests/dialects.4.html _output/tests/dialects.5.html _output/tests/dialects.tex _output/tests/dialects.xe.tex _output/tests/dialects.lua.tex _output/tests/directive-options.html _output/tests/directive-options.xe.tex _output/tests/display-flags.html _output/tests/doctests.out _output/tests/errors.lint.json _output/tests/errors.txt _output/tests/latex_formatting.tex _output/tests/literate.v _output/tests/literate.v.rst _output/tests/screenshot.html _output/tests/stylesheets.html _output/tests/stylesheets.part.tex _output/tests/syntax_highlighting.html
