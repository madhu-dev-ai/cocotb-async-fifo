import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer


async def reset(dut):
    dut.wrst_n.value = 0
    dut.rrst_n.value = 0
    dut.winc.value = 0
    dut.rinc.value = 0
    dut.wdata.value = 0
    await Timer(100, unit="ns")
    dut.wrst_n.value = 1
    dut.rrst_n.value = 1
    await Timer(50, unit="ns")


class FifoDriver:
    """Pushes data in on the write clock, pops data out on the read clock."""

    def __init__(self, dut):
        self.dut = dut

    async def write(self, data):
        self.dut.wdata.value = data
        self.dut.winc.value = 1
        while True:
            await RisingEdge(self.dut.wclk)
            if int(self.dut.wfull.value) == 0:   # write was accepted
                break
        self.dut.winc.value = 0

    async def read(self):
        self.dut.rinc.value = 1
        while True:
            await RisingEdge(self.dut.rclk)
            if int(self.dut.rempty.value) == 0:  # read was accepted
                break
        self.dut.rinc.value = 0


class FifoMonitor:
    """Watches both sides and tells subscribers about every real write and read."""

    def __init__(self, dut):
        self.dut = dut
        self.write_subs = []
        self.read_subs = []

    def start(self):
        cocotb.start_soon(self._watch_write())
        cocotb.start_soon(self._watch_read())

    async def _watch_write(self):
        while True:
            await RisingEdge(self.dut.wclk)
            if int(self.dut.winc.value) == 1 and int(self.dut.wfull.value) == 0:
                item = int(self.dut.wdata.value)
                for cb in self.write_subs:
                    cb(item)

    async def _watch_read(self):
        while True:
            await RisingEdge(self.dut.rclk)
            if int(self.dut.rinc.value) == 1 and int(self.dut.rempty.value) == 0:
                item = int(self.dut.rdata.value)
                for cb in self.read_subs:
                    cb(item)


class FifoScoreboard:
    """Python model: what goes in must come out, in the same order."""

    def __init__(self, dut):
        self.dut = dut
        self.expected = []
        self.checked = 0
        self.errors = 0

    def on_write(self, item):
        self.expected.append(item)

    def on_read(self, item):
        if not self.expected:
            self.errors += 1
            self.dut._log.error(f"Read {item:#x} but nothing was expected")
            return
        exp = self.expected.pop(0)
        if item != exp:
            self.errors += 1
            self.dut._log.error(f"Data mismatch: expected {exp:#x}, got {item:#x}")
        else:
            self.checked += 1


class FifoCoverage:
    """10 bins: did the test reach the interesting situations?"""

    BINS = [
        "empty_after_reset",
        "first_write",
        "became_full",
        "became_empty_after_read",
        "write_blocked_when_full",
        "read_blocked_when_empty",
        "write_and_read_together",
        "mid_level_4_to_12",
        "wrap_once",
        "wrap_many",
    ]

    def __init__(self, dut, scoreboard):
        self.dut = dut
        self.sb = scoreboard
        self.hits = {b: 0 for b in self.BINS}
        self.writes_total = 0

    def hit(self, name):
        self.hits[name] += 1

    def start(self):
        if int(self.dut.rempty.value) == 1:
            self.hit("empty_after_reset")
        cocotb.start_soon(self._sample_write_clock())
        cocotb.start_soon(self._sample_read_clock())

    def on_write(self, item):
        self.writes_total += 1
        if self.writes_total == 1:
            self.hit("first_write")
        if self.writes_total >= 17:
            self.hit("wrap_once")
        if self.writes_total >= 100:
            self.hit("wrap_many")
        if 4 <= len(self.sb.expected) <= 12:
            self.hit("mid_level_4_to_12")

    def on_read(self, item):
        if len(self.sb.expected) == 0:
            self.hit("became_empty_after_read")

    async def _sample_write_clock(self):
        while True:
            await RisingEdge(self.dut.wclk)
            winc = int(self.dut.winc.value)
            wfull = int(self.dut.wfull.value)
            rinc = int(self.dut.rinc.value)
            rempty = int(self.dut.rempty.value)
            if wfull == 1:
                self.hit("became_full")
            if winc == 1 and wfull == 1:
                self.hit("write_blocked_when_full")
            if winc == 1 and wfull == 0 and rinc == 1 and rempty == 0:
                self.hit("write_and_read_together")

    async def _sample_read_clock(self):
        while True:
            await RisingEdge(self.dut.rclk)
            if int(self.dut.rinc.value) == 1 and int(self.dut.rempty.value) == 1:
                self.hit("read_blocked_when_empty")

    def covered(self):
        return sum(1 for b in self.BINS if self.hits[b] > 0)

    def report(self):
        self.dut._log.info(f"Coverage: {self.covered()}/{len(self.BINS)} bins")
        for b in self.BINS:
            mark = "HIT " if self.hits[b] > 0 else "MISS"
            self.dut._log.info(f"  {mark} {b} ({self.hits[b]})")


async def make_env(dut):
    """Starts both clocks, resets the FIFO, builds and connects everything."""
    cocotb.start_soon(Clock(dut.wclk, 10, unit="ns").start())
    cocotb.start_soon(Clock(dut.rclk, 14, unit="ns").start())
    await reset(dut)

    driver = FifoDriver(dut)
    monitor = FifoMonitor(dut)
    scoreboard = FifoScoreboard(dut)
    coverage = FifoCoverage(dut, scoreboard)

    # scoreboard first, then coverage (coverage reads the scoreboard queue)
    monitor.write_subs.append(scoreboard.on_write)
    monitor.write_subs.append(coverage.on_write)
    monitor.read_subs.append(scoreboard.on_read)
    monitor.read_subs.append(coverage.on_read)

    coverage.start()
    monitor.start()
    return driver, monitor, scoreboard, coverage


@cocotb.test()
async def test_basic(dut):
    driver, monitor, sb, cov = await make_env(dut)

    async def writer():
        for i in range(20):
            await driver.write(0x10 + i)

    async def reader():
        for _ in range(20):
            await driver.read()

    w = cocotb.start_soon(writer())
    r = cocotb.start_soon(reader())
    await w
    await r

    for _ in range(5):
        await RisingEdge(dut.rclk)

    cov.report()
    dut._log.info(f"checked={sb.checked} errors={sb.errors}")
    assert sb.errors == 0, "Scoreboard found errors"
    assert sb.checked == 20, f"Expected 20 checks, got {sb.checked}"
    assert not sb.expected, "Some written items were never read"


@cocotb.test()
async def test_random(dut):
    """300 random items. Phases swap between 'writer fast' and 'reader fast',
    so the FIFO fills up, empties, and wraps around many times."""
    random.seed(1)
    driver, monitor, sb, cov = await make_env(dut)
    N = 300

    async def writer():
        for i in range(N):
            await driver.write(random.randint(0, 255))
            fast = ((i // 50) % 2 == 0)
            gap = random.randint(0, 1) if fast else random.randint(0, 6)
            for _ in range(gap):
                await RisingEdge(dut.wclk)

    async def reader():
        for i in range(N):
            await driver.read()
            slow = ((i // 50) % 2 == 0)
            gap = random.randint(0, 6) if slow else random.randint(0, 1)
            for _ in range(gap):
                await RisingEdge(dut.rclk)

    w = cocotb.start_soon(writer())
    r = cocotb.start_soon(reader())
    await w
    await r

    for _ in range(5):
        await RisingEdge(dut.rclk)

    cov.report()
    dut._log.info(f"checked={sb.checked} errors={sb.errors}")
    assert sb.errors == 0, "Scoreboard found errors"
    assert sb.checked == N, f"Expected {N} checks, got {sb.checked}"
    assert not sb.expected, "Some written items were never read"
    assert cov.covered() == len(cov.BINS), \
        f"Coverage incomplete: {cov.covered()}/{len(cov.BINS)}"