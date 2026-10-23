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


@cocotb.test()
async def test_basic(dut):
    # two different clocks
    cocotb.start_soon(Clock(dut.wclk, 10, unit="ns").start())
    cocotb.start_soon(Clock(dut.rclk, 14, unit="ns").start())

    await reset(dut)

    # after reset: empty, not full
    assert dut.rempty.value == 1, "FIFO should be empty after reset"
    assert dut.wfull.value == 0, "FIFO should not be full after reset"

    # write 5 values on the write clock
    sent = [0x11, 0x22, 0x33, 0x44, 0x55]
    for v in sent:
        await RisingEdge(dut.wclk)
        dut.wdata.value = v
        dut.winc.value = 1
    await RisingEdge(dut.wclk)
    dut.winc.value = 0

    # wait a few read clocks so the write pointer crosses over
    for _ in range(6):
        await RisingEdge(dut.rclk)

    # read 5 values on the read clock
    got = []
    for _ in sent:
        await RisingEdge(dut.rclk)
        while dut.rempty.value == 1:
            await RisingEdge(dut.rclk)
        got.append(int(dut.rdata.value))
        dut.rinc.value = 1
        await RisingEdge(dut.rclk)
        dut.rinc.value = 0

    dut._log.info(f"sent={sent} got={got}")
    assert got == sent, f"Mismatch: sent={sent} got={got}"