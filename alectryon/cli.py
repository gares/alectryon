# Copyright © 2019 Clément Pit-Claudel
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import argparse
import inspect
import os
import os.path
import re
import shutil
import sys

# Pipelines
# =========

def read_plain(_, fpath, fname):
    if fname == "-":
        return sys.stdin.read()
    with open(fpath, encoding="utf-8") as f:
        return f.read()

def read_json(_, fpath, fname):
    from .json import load
    if fname == "-":
        return load(sys.stdin)
    with open(fpath, encoding="utf-8") as f:
        return load(f)

def parse_plain(contents):
    return [contents]

def _catch_parsing_errors(fpath, k, *args):
    from .literate import ParsingError
    try:
        return k(*args)
    except ParsingError as e:
        raise ValueError("{}:{}".format(fpath, e))

def code_to_rst(code, fpath, point, marker, input_language):
    if input_language == "coq":
        from .literate import coq2rst_marked as converter
    else:
        assert False
    return _catch_parsing_errors(fpath, converter, code, point, marker)

def rst_to_code(rst, fpath, point, marker, backend):
    if backend in ("coq", "coq+rst"):
        from .literate import rst2coq_marked as converter
    else:
        assert False
    return _catch_parsing_errors(fpath, converter, rst, point, marker)

def annotate_chunks(chunks, fpath, input_language, prover_config,
                    cache_directory, cache_compression):
    from .core import get_prover
    from .json import CacheSet
    prover, config = get_prover(input_language), prover_config[input_language]
    with CacheSet(cache_directory, fpath, cache_compression) as caches:
        return caches[input_language].update(chunks, prover, config)

def register_docutils(v, args):
    from . import docutils
    docutils.AlectryonTransform.PROVER_CONFIG = args.prover_config
    docutils.CACHE_DIRECTORY = args.cache_directory
    docutils.CACHE_COMPRESSION = args.cache_compression
    docutils.HTML_MINIFICATION = args.html_minification
    docutils.LONG_LINE_THRESHOLD = args.long_line_threshold
    docutils.setup()
    return v

def _gen_docutils(source, fpath,
                  Parser, Reader, Writer,
                  settings_overrides):
    from docutils.core import publish_string

    # The encoding/decoding dance below happens because setting output_encoding
    # to "unicode" causes reST to generate a bad <meta> tag, and setting
    # input_encoding to "unicode" breaks the ‘.. include’ directive.

    # Setting ``traceback`` unconditionally allows us to catch and report errors
    # from our own docutils components and avoid asking users to make a report
    # to the docutils mailing list.

    settings_overrides = {
        'traceback': True,
        'stylesheet_path': None,
        'input_encoding': 'utf-8',
        'output_encoding': 'utf-8',
        **settings_overrides
    }

    parser = Parser()
    return publish_string(
        source=source.encode("utf-8"),
        source_path=fpath, destination_path=None,
        reader=Reader(parser), reader_name=None,
        parser=parser, parser_name=None,
        writer=Writer(), writer_name=None,
        settings=None, settings_spec=None,
        settings_overrides=settings_overrides, config_section=None,
        enable_exit_status=True).decode("utf-8")

def gen_docutils(src, frontend, backend, fpath,
                 html_dialect, latex_dialect,
                 webpage_style, include_banner, include_vernums,
                 assets):
    from .docutils import get_pipeline

    pipeline = get_pipeline(frontend, backend, html_dialect, latex_dialect)
    assets.extend(pipeline.translator.ASSETS)

    settings_overrides = {
        'alectryon_banner': include_banner,
        'alectryon_vernums': include_vernums,
        'alectryon_webpage_style': webpage_style,
    }

    return _gen_docutils(src, fpath,
                         pipeline.parser, pipeline.reader, pipeline.writer,
                         settings_overrides)

def _docutils_cmdline(description, frontend, backend):
    import locale
    locale.setlocale(locale.LC_ALL, '')

    from docutils.core import publish_cmdline, default_description
    from .docutils import setup, get_pipeline

    setup()

    pipeline = get_pipeline(frontend, backend, "html4", "pdflatex")
    publish_cmdline(
        parser=pipeline.parser(), writer=pipeline.writer(),
        settings_overrides={'stylesheet_path': None},
        description="{} {}".format(description, default_description)
    )

def lint_docutils(source, fpath, frontend):
    from io import StringIO
    from docutils.utils import new_document
    from docutils.frontend import OptionParser
    from docutils.utils import Reporter
    from .docutils import JsErrorPrinter, get_parser

    parser_class = get_parser(frontend)
    settings = OptionParser(components=(parser_class,)).get_default_values()
    settings.traceback = True
    observer = JsErrorPrinter(StringIO(), settings)
    document = new_document(fpath, settings)

    document.reporter.report_level = 0 # Report all messages
    document.reporter.halt_level = Reporter.SEVERE_LEVEL + 1 # Do not exit early
    document.reporter.stream = False # Disable textual reporting
    document.reporter.attach_observer(observer)
    parser_class().parse(source, document)

    return observer.stream.getvalue()

def _scrub_fname(fname):
    import re
    return re.sub("[^-a-zA-Z0-9]", "-", fname)

def apply_transforms(annotated, input_language):
    from .transforms import default_transform
    for chunk in annotated:
        yield default_transform(chunk, input_language)

def gen_html_snippets(annotated, fname, input_language, html_minification):
    from .html import HtmlGenerator
    from .pygments import make_highlighter
    highlighter = make_highlighter("html", input_language)
    return HtmlGenerator(highlighter, _scrub_fname(fname), html_minification).gen(annotated)

def gen_latex_snippets(annotated, input_language):
    from .latex import LatexGenerator
    from .pygments import make_highlighter
    highlighter = make_highlighter("latex", input_language)
    return LatexGenerator(highlighter).gen(annotated)

COQDOC_OPTIONS = ['--body-only', '--no-glob', '--no-index', '--no-externals',
                  '-s', '--html', '--stdout', '--utf8']

def _run_coqdoc(coq_snippets, coqdoc_bin=None):
    """Get the output of coqdoc on coq_code."""
    from shutil import rmtree
    from tempfile import mkstemp, mkdtemp
    from subprocess import check_output
    coqdoc_bin = coqdoc_bin or os.path.join(os.getenv("COQBIN", ""), "coqdoc")
    dpath = mkdtemp(prefix="alectryon_coqdoc_")
    fd, filename = mkstemp(prefix="alectryon_coqdoc_", suffix=".v", dir=dpath)
    try:
        for snippet in coq_snippets:
            os.write(fd, snippet.encode("utf-8"))
            os.write(fd, b"\n(* --- *)\n") # Separator to prevent fusing
        os.close(fd)
        coqdoc = [coqdoc_bin, *COQDOC_OPTIONS, "-d", dpath, filename]
        return check_output(coqdoc, cwd=dpath, timeout=10).decode("utf-8")
    finally:
        rmtree(dpath)

def _gen_coqdoc_html(coqdoc_fragments):
    from bs4 import BeautifulSoup
    coqdoc_output = _run_coqdoc(fr.contents for fr in coqdoc_fragments)
    soup = BeautifulSoup(coqdoc_output, "html.parser")
    docs = soup.find_all(class_='doc')
    coqdoc_comments = [c for c in coqdoc_fragments if not c.special]
    if len(docs) != len(coqdoc_comments):
        from pprint import pprint
        print("Coqdoc mismatch:", file=sys.stderr)
        pprint(list(zip(coqdoc_comments, docs)))
        raise AssertionError()
    return docs

def _gen_html_snippets_with_coqdoc(annotated, fname, input_language, html_minification):
    from dominate.util import raw
    from .html import HtmlGenerator
    from .pygments import make_highlighter
    from .transforms import isolate_coqdoc, default_transform, CoqdocFragment

    highlighter = make_highlighter("html", input_language)
    writer = HtmlGenerator(highlighter, _scrub_fname(fname), html_minification)

    parts = [part for fragments in annotated
             for part in isolate_coqdoc(fragments)]
    coqdoc = [part for part in parts
              if isinstance(part, CoqdocFragment)]
    coqdoc_html = iter(_gen_coqdoc_html(coqdoc))

    for part in parts:
        if isinstance(part, CoqdocFragment):
            if not part.special:
                yield [raw(str(next(coqdoc_html, None)))]
        else:
            fragments = default_transform(part.fragments, "coq")
            yield writer.gen_fragments(fragments)

def gen_html_snippets_with_coqdoc(annotated, html_classes, fname, input_language, html_minification):
    html_classes.append("coqdoc")
    # ‘return’ instead of ‘yield from’ to update html_classes eagerly
    return _gen_html_snippets_with_coqdoc(annotated, fname, input_language, html_minification)

def copy_assets(state, assets, copy_fn, output_directory):
    from .html import ASSETS

    for name in assets:
        src = os.path.join(ASSETS.PATH, name)
        dst = os.path.join(output_directory, name)
        if copy_fn is not shutil.copy:
            try:
                os.unlink(dst)
            except FileNotFoundError:
                pass
        try:
            copy_fn(src, dst)
        except shutil.SameFileError:
            pass

    return state

def dump_html_standalone(snippets, fname, webpage_style,
                         html_minification, include_banner, include_vernums,
                         assets, html_classes, input_language):
    from dominate import tags, document
    from dominate.util import raw
    from . import GENERATOR
    from .pygments import HTML_FORMATTER
    from .html import ASSETS, ADDITIONAL_HEADS, JS_UNMINIFY, gen_banner, wrap_classes

    doc = document(title=fname)
    doc.set_attribute("class", "alectryon-standalone")

    doc.head.add(tags.meta(charset="utf-8"))
    doc.head.add(tags.meta(name="generator", content=GENERATOR))

    for hd in ADDITIONAL_HEADS:
        doc.head.add(raw(hd))
    if html_minification:
        doc.head.add(raw(JS_UNMINIFY))
    for css in ASSETS.ALECTRYON_CSS:
        doc.head.add(tags.link(rel="stylesheet", href=css))
    for link in (ASSETS.IBM_PLEX_CDN, ASSETS.FIRA_CODE_CDN):
        doc.head.add(raw(link))
    for js in ASSETS.ALECTRYON_JS:
        doc.head.add(tags.script(src=js))

    assets.extend(ASSETS.ALECTRYON_CSS)
    assets.extend(ASSETS.ALECTRYON_JS)

    pygments_css = HTML_FORMATTER.get_style_defs('.highlight')
    doc.head.add(tags.style(pygments_css, type="text/css"))

    if html_minification:
        html_classes.append("minified")

    cls = wrap_classes(webpage_style, *html_classes)
    root = doc.body.add(tags.article(cls=cls))
    if include_banner:
        from .core import get_prover
        prover = get_prover(input_language)
        root.add(raw(gen_banner([prover.version_info()], include_vernums)))
    for snippet in snippets:
        root.add(snippet)

    return doc.render(pretty=False)

def encode_json(obj):
    from .json import PlainSerializer
    return PlainSerializer.encode(obj)

def dump_json(js):
    from json import dumps
    return dumps(js, indent=4)

def dump_html_snippets(snippets):
    s = ""
    for snippet in snippets:
        s += snippet.render(pretty=True)
        s += "<!-- alectryon-block-end -->\n"
    return s

def dump_latex_snippets(snippets):
    s = ""
    for snippet in snippets:
        s += str(snippet)
        s += "\n%% alectryon-block-end\n"
    return s

def write_output(ext, contents, fname, output, output_directory, strip_re):
    if output == "-" or (output is None and fname == "-"):
        sys.stdout.write(contents)
    else:
        if not output:
            fname = strip_re.sub("", fname)
            output = os.path.join(output_directory, fname + ext)
        with open(output, mode="w", encoding="utf-8") as f:
            f.write(contents)

def write_file(ext, strip):
    strip = re.compile("(" + "|".join(re.escape(ext) for ext in strip) + ")*\\Z")
    return lambda contents, fname, output, output_directory: \
        write_output(ext, contents, fname, output, output_directory,
                     strip_re=strip)

# No ‘apply_transforms’ in JSON pipelines: (we save the prover output without
# modifications).
PIPELINES = {
    'coq.json': {
        'json':
        (read_json, annotate_chunks, encode_json, dump_json,
         write_file(".io.json", strip=(".json",))),
        'snippets-html':
        (read_json, annotate_chunks, apply_transforms, gen_html_snippets,
         dump_html_snippets, write_file(".snippets.html", strip=(".v", ".json",))),
        'snippets-latex':
        (read_json, annotate_chunks, apply_transforms, gen_latex_snippets,
         dump_latex_snippets, write_file(".snippets.tex", strip=(".v", ".json",)))
    },
    'lean3.json': {
        'json':
        (read_json, annotate_chunks, encode_json, dump_json,
         write_file(".io.json", strip=(".json",))),
        'snippets-html':
        (read_json, annotate_chunks, apply_transforms,
         gen_html_snippets, dump_html_snippets,
         write_file(".snippets.html", strip=(".lean", ".lean3", ".json",))),
        'snippets-latex':
        (read_json, annotate_chunks, apply_transforms,
         gen_latex_snippets, dump_latex_snippets,
         write_file(".snippets.tex", strip=(".lean", ".lean3", ".json",)))
    },
    'coq': {
        'null':
        (read_plain, parse_plain, annotate_chunks),
        'webpage':
        (read_plain, parse_plain, annotate_chunks, apply_transforms,
         gen_html_snippets, dump_html_standalone, copy_assets,
         write_file(".html", strip=())),
        'snippets-html':
        (read_plain, parse_plain, annotate_chunks, apply_transforms,
         gen_html_snippets, dump_html_snippets,
         write_file(".snippets.html", strip=(".v",))),
        'snippets-latex':
        (read_plain, parse_plain, annotate_chunks, apply_transforms,
         gen_latex_snippets, dump_latex_snippets,
         write_file(".snippets.tex", strip=(".v",))),
        'lint':
        (read_plain, register_docutils, lint_docutils,
         write_file(".lint.json", strip=(".v",))),
        'rst':
        (read_plain, code_to_rst, write_file(".rst", strip=())),
        'json':
        (read_plain, parse_plain, annotate_chunks, encode_json, dump_json,
         write_file(".io.json", strip=()))
    },
    'lean3': {
        'null':
        (read_plain, parse_plain, annotate_chunks),
        'webpage':
        (read_plain, parse_plain, annotate_chunks, apply_transforms,
         gen_html_snippets, dump_html_standalone, copy_assets,
         write_file(".html", strip=())),
        'snippets-html':
        (read_plain, parse_plain, annotate_chunks, apply_transforms,
         gen_html_snippets, dump_html_snippets,
         write_file(".snippets.html", strip=(".lean", ".lean3"))),
        'snippets-latex':
        (read_plain, parse_plain, annotate_chunks, apply_transforms,
         gen_latex_snippets, dump_latex_snippets,
         write_file(".snippets.tex", strip=(".lean", ".lean3"))),
        'json':
        (read_plain, parse_plain, annotate_chunks, encode_json, dump_json,
         write_file(".io.json", strip=()))
    },
    'coq+rst': {
        'webpage':
        (read_plain, register_docutils, gen_docutils, copy_assets,
         write_file(".html", strip=(".v", ".rst"))),
        'latex':
        (read_plain, register_docutils, gen_docutils, copy_assets,
         write_file(".tex", strip=(".v", ".rst"))),
        'lint':
        (read_plain, register_docutils, lint_docutils,
         write_file(".lint.json", strip=(".v", ".rst"))),
        'rst':
        (read_plain, code_to_rst, write_file(".v.rst", strip=(".v", ".rst"))),
    },
    'coqdoc': {
        'webpage':
        (read_plain, parse_plain, annotate_chunks, # transforms applied later
         gen_html_snippets_with_coqdoc, dump_html_standalone, copy_assets,
         write_file(".html", strip=(".v",))),
    },
    'rst': {
        'webpage':
        (read_plain, register_docutils, gen_docutils, copy_assets,
         write_file(".html", strip=(".v", ".lean", ".lean3", ".rst"))),
        'latex':
        (read_plain, register_docutils, gen_docutils, copy_assets,
         write_file(".tex", strip=(".v", ".lean", ".lean3", ".rst"))),
        'lint':
        (read_plain, register_docutils, lint_docutils,
         write_file(".lint.json", strip=(".v", ".lean", ".lean3", ".rst"))),
        'coq':
        (read_plain, rst_to_code,
         write_file(".v", strip=(".v", ".lean", ".lean3", ".rst"))),
        'coq+rst':
        (read_plain, rst_to_code,
         write_file(".v", strip=(".v", ".lean", ".lean3", ".rst")))
    },
    'md': {
        'webpage':
        (read_plain, register_docutils, gen_docutils, copy_assets,
         write_file(".html", strip=(".v", ".lean", ".lean3", ".md"))),
        'latex':
        (read_plain, register_docutils, gen_docutils, copy_assets,
         write_file(".tex", strip=(".v", ".lean", ".lean3", ".md"))),
        'lint':
        (read_plain, register_docutils, lint_docutils,
         write_file(".lint.json", strip=(".v", ".lean", ".lean3", ".md")))
    }
}

# CLI
# ===

FRONTENDS_BY_EXTENSION = [
    ('.v', 'coq+rst'), ('.lean', 'lean3'), ('.lean3', 'lean3'),
    ('.v.json', 'coq.json'), ('.lean3.json', 'lean3.json'),
    ('.rst', 'rst'), ('.md', 'md')
]
BACKENDS_BY_EXTENSION = [
    ('.v', 'coq'), ('.lean', 'lean3'),
    ('.json', 'json'), ('.rst', 'rst'),
    ('.lint.json', 'lint'),
    ('.snippets.html', 'snippets-html'),
    ('.snippets.tex', 'snippets-latex'),
    ('.v.html', 'webpage'), ('.html', 'webpage'),
    ('.v.tex', 'latex'), ('.tex', 'latex')
]

DEFAULT_BACKENDS = {
    'coq.json': 'json',
    'lean3.json': 'json',
    'coq': 'webpage',
    'coqdoc': 'webpage',
    'coq+rst': 'webpage',
    'lean3': 'webpage',
    'rst': 'webpage',
    'md': 'webpage',
}

INPUT_LANGUAGE_BY_FRONTEND = {
    "coq": "coq",
    "coqdoc": "coq",
    "coq+rst": "coq",
    "rst": None,
    "md": None,
    "lean3": "lean3",
    "coq.json": "coq",
    "lean3.json": "lean3",
}

def infer_mode(fpath, kind, arg, table):
    for (ext, mode) in table:
        if fpath.endswith(ext):
            return mode
    MSG = """{}: Not sure what to do with {!r}.
Try passing {}?"""
    raise argparse.ArgumentTypeError(MSG.format(kind, fpath, arg))

def infer_frontend(fpath):
    return infer_mode(fpath, "input", "--frontend", FRONTENDS_BY_EXTENSION)

def infer_backend(frontend, out_fpath):
    if out_fpath:
        return infer_mode(out_fpath, "output", "--backend", BACKENDS_BY_EXTENSION)
    return DEFAULT_BACKENDS[frontend]

def resolve_pipeline(fpath, args):
    frontend = args.frontend or infer_frontend(fpath)

    assert frontend in PIPELINES
    supported_backends = PIPELINES[frontend]

    backend = args.backend or infer_backend(frontend, args.output)
    if backend not in supported_backends:
        MSG = """argument --backend: Frontend {!r} does not support backend {!r}: \
expecting one of {}"""
        raise argparse.ArgumentTypeError(MSG.format(
            frontend, backend, ", ".join(map(repr, supported_backends))))

    return (frontend, backend, supported_backends[backend])

COPY_FUNCTIONS = {
    "copy": shutil.copy,
    "symlink": os.symlink,
    "hardlink": os.link,
    "none": None
}

def post_process_arguments(parser, args):
    if len(args.input) > 1 and args.output:
        parser.error("argument --output: Not valid with multiple inputs")

    if args.stdin_filename and "-" not in args.input:
        parser.error("argument --stdin-filename: input must be '-'")

    for dirpath in args.coq_args_I:
        args.sertop_args.extend(("-I", dirpath))
    for pair in args.coq_args_R:
        args.sertop_args.extend(("-R", ",".join(pair)))
    for pair in args.coq_args_Q:
        args.sertop_args.extend(("-Q", ",".join(pair)))

    # argparse applies ‘type’ before ‘choices’, so we do the conversion here
    args.copy_fn = COPY_FUNCTIONS[args.copy_fn]

    args.point, args.marker = args.mark_point
    if args.point is not None:
        try:
            args.point = int(args.point)
        except ValueError:
            MSG = "argument --mark-point: Expecting a number, not {!r}"
            parser.error(MSG.format(args.point))

    args.prover_config = {
        "coq": {"args": args.sertop_args},
        "lean3": {"args": ()},
    }
    delattr(args, "sertop_args")

    args.assets = []
    args.html_classes = []
    args.pipelines = [(fpath, resolve_pipeline(fpath, args))
                      for fpath in args.input]

    return args

def build_parser():
    parser = argparse.ArgumentParser(
        description="""\
Annotate segments of Coq code with responses and goals.
Take input in Coq, reStructuredText, Markdown, or JSON \
and produce reStructuredText, HTML, LaTeX, or JSON output.""",
        fromfile_prefix_chars='@')

    in_ = parser.add_argument_group("Input configuration")

    INPUT_FILES_HELP = "Input files"
    in_.add_argument("input", nargs="+", help=INPUT_FILES_HELP)

    INPUT_STDIN_NAME_HELP = "Name of file passed on stdin, if any"
    in_.add_argument("--stdin-filename", default=None,
                     help=INPUT_STDIN_NAME_HELP)

    FRONTEND_HELP = "Choose a frontend. Defaults: "
    FRONTEND_HELP += "; ".join("{!r} → {}".format(ext, frontend)
                               for ext, frontend in FRONTENDS_BY_EXTENSION)
    FRONTEND_CHOICES = sorted(PIPELINES.keys())
    in_.add_argument("--frontend", default=None, choices=FRONTEND_CHOICES,
                     help=FRONTEND_HELP)


    out = parser.add_argument_group("Output configuration")

    BACKEND_HELP = "Choose a backend. Supported: "
    BACKEND_HELP += "; ".join(
        "{} → {{{}}}".format(frontend, ", ".join(sorted(backends)))
        for frontend, backends in PIPELINES.items())
    BACKEND_CHOICES = sorted(set(b for _, bs in PIPELINES.items() for b in bs))
    out.add_argument("--backend", default=None, choices=BACKEND_CHOICES,
                     help=BACKEND_HELP)

    OUT_FILE_HELP = "Set the output file (default: computed based on INPUT)."
    out.add_argument("-o", "--output", default=None,
                     help=OUT_FILE_HELP)

    OUT_DIR_HELP = "Set the output directory (default: same as each INPUT)."
    out.add_argument("--output-directory", default=None,
                     help=OUT_DIR_HELP)

    COPY_ASSETS_HELP = ("Chose the method to use to copy assets " +
                        "along the generated file(s) when creating webpages.")
    out.add_argument("--copy-assets", choices=list(COPY_FUNCTIONS.keys()),
                     default="copy", dest="copy_fn",
                     help=COPY_ASSETS_HELP)

    MARK_POINT_HELP = "Mark a point in the output with a given marker."
    out.add_argument("--mark-point", nargs=2, default=(None, None),
                     metavar=("POINT", "MARKER"),
                     help=MARK_POINT_HELP)

    NO_HEADER_HELP = "Do not insert a header with usage instructions in webpages."
    out.add_argument("--no-header", action='store_false',
                     dest="include_banner", default="True",
                     help=NO_HEADER_HELP)

    NO_VERSION_NUMBERS = "Omit version numbers in meta tags and headers."
    out.add_argument("--no-version-numbers", action='store_false',
                     dest="include_vernums", default=True,
                     help=NO_VERSION_NUMBERS)

    cache_out = parser.add_argument_group("Cache configuration")

    CACHE_DIRECTORY_HELP = ("Cache prover output in DIRECTORY.")
    cache_out.add_argument("--cache-directory", default=None, metavar="DIRECTORY",
                           help=CACHE_DIRECTORY_HELP)

    CACHE_COMPRESSION_HELP = ("Compress caches.")
    CACHE_COMPRESSION_CHOICES = ("none", "gzip", "xz")
    cache_out.add_argument("--cache-compression", nargs='?',
                           default=None, const="xz",
                           choices=CACHE_COMPRESSION_CHOICES,
                           help=CACHE_COMPRESSION_HELP)

    html_out = parser.add_argument_group("HTML output configuration")

    WEBPAGE_STYLE_HELP = "Choose a style for standalone webpages."
    WEBPAGE_STYLE_CHOICES = ("centered", "floating", "windowed")
    html_out.add_argument("--webpage-style", default="centered",
                          choices=WEBPAGE_STYLE_CHOICES,
                          help=WEBPAGE_STYLE_HELP)

    HTML_MINIFICATION_HELP = (
        "Minify HTML files using backreferences for repeated content. "
        "(Backreferences are automatically expanded on page load,"
        " using a very small amount of JavaScript code.)"
    )
    html_out.add_argument("--html-minification", action='store_true',
                          default=False,
                          help=HTML_MINIFICATION_HELP)

    HTML_DIALECT_HELP = "Choose which HTML dialect to use."
    HTML_DIALECT_CHOICES = ("html4", "html5")
    html_out.add_argument("--html-dialect", default="html4",
                          choices=HTML_DIALECT_CHOICES,
                          help=HTML_DIALECT_HELP)

    latex_out = parser.add_argument_group("LaTeX output configuration")

    LATEX_DIALECT_HELP = "Choose which LaTeX dialect to use."
    LATEX_DIALECT_CHOICES = ("pdflatex", "xelatex", "lualatex")
    latex_out.add_argument("--latex-dialect", default="pdflatex",
                           choices=LATEX_DIALECT_CHOICES,
                           help=LATEX_DIALECT_HELP)

    subp = parser.add_argument_group("SerAPI process configuration")

    SERTOP_ARGS_HELP = "Pass a single argument to SerAPI (e.g. -Q dir,lib)."
    subp.add_argument("--sertop-arg", dest="sertop_args",
                      action="append", default=[],
                      metavar="SERAPI_ARG",
                      help=SERTOP_ARGS_HELP)

    I_HELP = "Pass -I DIR to the SerAPI subprocess."
    subp.add_argument("-I", "--ml-include-path", dest="coq_args_I",
                      metavar="DIR", nargs=1, action="append",
                      default=[], help=I_HELP)

    Q_HELP = "Pass -Q DIR COQDIR to the SerAPI subprocess."
    subp.add_argument("-Q", "--load-path", dest="coq_args_Q",
                      metavar=("DIR", "COQDIR"), nargs=2, action="append",
                      default=[], help=Q_HELP)

    R_HELP = "Pass -R DIR COQDIR to the SerAPI subprocess."
    subp.add_argument("-R", "--rec-load-path", dest="coq_args_R",
                      metavar=("DIR", "COQDIR"), nargs=2, action="append",
                      default=[], help=R_HELP)

    warn_out = parser.add_argument_group("Warnings configuration")

    LL_THRESHOLD_HELP = "Warn on lines longer than this threshold (docutils)."
    warn_out.add_argument("--long-line-threshold", type=int,
                          default=72, help=LL_THRESHOLD_HELP)

    debug = parser.add_argument_group("Debugging options")

    EXPECT_UNEXPECTED_HELP = "Ignore unexpected output from SerAPI"
    debug.add_argument("--expect-unexpected", action="store_true",
                       default=False, help=EXPECT_UNEXPECTED_HELP)

    DEBUG_HELP = "Print communications with prover process."
    debug.add_argument("--debug", action="store_true",
                       default=False, help=DEBUG_HELP)

    TRACEBACK_HELP = "Print error traces."
    debug.add_argument("--traceback", action="store_true",
                       default=False, help=TRACEBACK_HELP)

    return parser

def parse_arguments():
    parser = build_parser()
    return post_process_arguments(parser, parser.parse_args())


# Entry point
# ===========

def call_pipeline_step(step, state, ctx):
    params = list(inspect.signature(step).parameters.keys())[1:]
    return step(state, **{p: ctx[p] for p in params})

def build_context(fpath, frontend, backend, args):
    if fpath == "-":
        fname, fpath = "-", (args.stdin_filename or "-")
    else:
        fname = os.path.basename(fpath)

    ctx = {"args": args, **vars(args),
           "fpath": fpath, "fname": fname,
           "frontend": frontend, "backend": backend,
           "input_language": INPUT_LANGUAGE_BY_FRONTEND[frontend]}

    if args.output_directory is None:
        if fname == "-":
            ctx["output_directory"] = "."
        else:
            ctx["output_directory"] = os.path.dirname(os.path.abspath(fpath))

    return ctx

def except_hook(etype, value, tb):
    from traceback import TracebackException
    for line in TracebackException(etype, value, tb, capture_locals=True).format():
        print(line, file=sys.stderr)

def process_pipelines(args):
    if args.debug:
        from . import core
        core.DEBUG = True

    if args.traceback:
        from . import core
        core.TRACEBACK = True
        sys.excepthook = except_hook

    if args.expect_unexpected:
        from . import serapi
        serapi.SerAPI.EXPECT_UNEXPECTED = True

    if args.output_directory:
        os.makedirs(os.path.realpath(args.output_directory), exist_ok=True)

    for fpath, (frontend, backend, pipeline) in args.pipelines:
        state, ctx = None, build_context(fpath, frontend, backend, args)
        for step in pipeline:
            state = call_pipeline_step(step, state, ctx)

def main():
    try:
        args = parse_arguments()
        process_pipelines(args)
    except (ValueError, FileNotFoundError, ImportError, argparse.ArgumentTypeError) as e:
        from . import core
        if core.TRACEBACK:
            raise e
        MSG = "Exiting early due to an error; use --traceback to diagnose."
        print(MSG, file=sys.stderr)
        print(str(e), file=sys.stderr)
        sys.exit(1)

# Alternative CLIs
# ================

def rstcoq2html():
    DESCRIPTION = 'Build an HTML document from an Alectryon Coq file.'
    _docutils_cmdline(DESCRIPTION, "coq+rst", "webpage")

def coqrst2html():
    DESCRIPTION = 'Build an HTML document from an Alectryon reStructuredText file.'
    _docutils_cmdline(DESCRIPTION, "rst", "webpage")

def rstcoq2latex():
    DESCRIPTION = 'Build a LaTeX document from an Alectryon Coq file.'
    _docutils_cmdline(DESCRIPTION, "coq+rst", "latex")

def coqrst2latex():
    DESCRIPTION = 'Build a LaTeX document from an Alectryon reStructuredText file.'
    _docutils_cmdline(DESCRIPTION, "rst", "latex")
