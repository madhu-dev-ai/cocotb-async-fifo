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


async def make_env(dut):
    """Starts both clocks, resets the FIFO, builds and connects everything."""
    cocotb.start_soon(Clock(dut.wclk, 10, unit="ns").start())
    cocotb.start_soon(Clock(dut.rclk, 14, unit="ns").start())
    await reset(dut)

    driver = FifoDriver(dut)
    monitor = FifoMonitor(dut)
    scoreboard = FifoScoreboard(dut)
    monitor.write_subs.append(scoreboard.on_write)
    monitor.read_subs.append(scoreboard.on_read)
    monitor.start()
    return driver, monitor, scoreboard


@cocotb.test()
async def test_basic(dut):
    driver, monitor, sb = await make_env(dut)

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

    dut._log.info(f"checked={sb.checked} errors={sb.errors}")
    assert sb.errors == 0, "Scoreboard found errors"
    assert sb.checked == 20, f"Expected 20 checks, got {sb.checked}"
    assert not sb.expected, "Some written items were never read"