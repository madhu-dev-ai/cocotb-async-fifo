SIM ?= icarus
TOPLEVEL_LANG ?= verilog

VERILOG_SOURCES = $(CURDIR)/async_fifo.v

COCOTB_TOPLEVEL = async_fifo
COCOTB_TEST_MODULES = test_async_fifo

include $(shell cocotb-config --makefiles)/Makefile.sim