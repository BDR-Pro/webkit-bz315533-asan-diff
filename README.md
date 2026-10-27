# webkit-bz315533-asan-diff

AddressSanitizer differential harness for upstream
[WebKit bug 315533](https://bugs.webkit.org/show_bug.cgi?id=315533) —
"Heap-use-after-free of RemoteLayerTreeEventDispatcher's RunLoop::Timer on
the scrolling thread" — fixed by commit
`2df698f59386b2ffccd45c7ef28422b69eba8c44`
(canonical: <https://commits.webkit.org/319667@main>).

## What this repository does

Manual-trigger GitHub Actions workflow (`stage-b-315533`) that runs two
macOS runners in parallel:

| Leg | WebKit revision | Meaning |
|---|---|---|
| `prefix` | `55d9d9007f54ee61fa38accb59cd88a8d4075847` (fix **parent**) | still contains the use-after-free |
| `fixed` | `2df698f59386b2ffccd45c7ef28422b69eba8c44` (the fix) | timer destroyed on the scrolling thread from `invalidate()` |

Each leg:

1. shallow-clones `WebKit/WebKit` at the pinned revision,
2. builds the Mac port with AddressSanitizer
   (`Tools/Scripts/build-webkit --release --asan`),
3. imports the regression test
   `LayoutTests/fast/scrolling/mac/event-dispatcher-timer-close-crash.html`
   from the fix commit (it does not exist at the parent revision),
4. runs it through WebKitTestRunner
   (`Tools/Scripts/run-webkit-tests`),
5. uploads the results tree + ASan evidence as artifacts.

## Expected differential

- **`prefix` leg:** the in-flight `CFRunLoopTimer` callback on the scrolling
  thread dispatches through the freed `RunLoop::TimerBase` — a
  `heap-use-after-free` in
  `RunLoop::TimerBase::start()::$_0::__invoke`
  (the attribution quoted verbatim in the fix commit message), i.e. the test
  crashes the UI process.
- **`fixed` leg:** the same test passes.

The pair is the memory-safety class evidence for the bug *without* needing
any vendor crash telemetry: same allocator, same object, same threads, and
the one-commit delta that closes it.

## Notes

- Everything cloned, built and run here is upstream public WebKit source.
  No proprietary code is involved.
- macOS runners are required because `RemoteLayerTreeEventDispatcher` is
  `PLATFORM(MAC)`-guarded (CoreFoundation run-loop timers).
- Everything is digest-pinned in the workflow; the workflow itself is
  manual-trigger only (`workflow_dispatch`).