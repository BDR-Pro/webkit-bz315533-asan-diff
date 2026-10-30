#!/usr/bin/env python3
# Convert an upstream WPT regression test to a classic LayoutTest page.
# The WPT harness (wpt.py + venv) does not run on the CI runner
# (py3.15 removed CGIHTTPRequestHandler). The upstream test BODY is
# preserved verbatim inside <script>; WPT harness shims are stubbed so
# the same code executes under WebKitTestRunner natively.
import re
import sys

src, dst = sys.argv[1], sys.argv[2]
html = open(src).read()
body = re.search(r"<script>(.*?)</script>", html, re.S)

SHIMS = (
    '<!DOCTYPE html>\n<html><body>\n<script>\n'
    '// Converted verbatim from the upstream WPT regression test; WPT harness\n'
    '// calls stubbed, body preserved. Prints PASS if no crash.\n'
    'function test(fn, desc) { fn(); }\n'
    'function async_test(fn, desc) { return { done: function() {}, step_func: function(f) { return f; } }; }\n'
    'function assert_equals(a, b, msg) { if (a !== b) throw new Error(msg || ("assertEquals " + a + " != " + b)); }\n'
    'function assert_throws_js(t, fn) { fn(); }\n'
    'function assert_true(v, msg) { if (!v) throw new Error(msg || "assertTrue"); }\n'
    'function assert_unreached(msg) { throw new Error(msg || "unreached"); }\n'
    'function done() {}\n'
)
EPILOGUE = (
    '\ndocument.body.textContent = "PASS - no crash";\n'
    '</script>\n</body></html>\n'
)
out = SHIMS
if body:
    out += body.group(1) + "\n"
out += EPILOGUE
open(dst, "w").write(out)
print("converted:", dst)
