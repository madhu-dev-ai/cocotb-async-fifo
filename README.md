\# cocotb-async-fifo

![test](https://github.com/madhu-dev-ai/cocotb-async-fifo/actions/workflows/test.yml/badge.svg)



Verification of an asynchronous FIFO (write clock and read clock are different) using a UVM-style layered testbench written in cocotb (Python) with Icarus Verilog.



\## What is verified



\- Design: 16-deep, 8-bit FIFO with Gray-code pointers and two-flop synchronizers between the clock domains

\- Write clock 10 ns, read clock 14 ns (different on purpose)



\## Testbench structure



| Class | Job |

|-------|-----|

| FifoDriver | Pushes data on the write clock, pops data on the read clock |

| FifoMonitor | Watches both sides and reports every accepted write and read |

| FifoScoreboard | Python queue: data out must match data in, same order |

| FifoCoverage | 10 bins: full, empty, blocked write, blocked read, simultaneous write and read, mid level, wrap-around |



\## Tests



\- test\_basic: 20 items, directed

\- test\_random: 300 random items, with phases that switch between a fast writer and a fast reader, so the FIFO fills up, empties and wraps many times. It reaches 10/10 coverage bins.

\- Both tests have a 200 us simulation timeout, so a hung design fails cleanly instead of running forever.



\## Bug stories



\*\*Bug 1: wrong Gray-code pointer.\*\* I changed the write pointer so it was plain binary and not Gray code. test\_basic still passed, because 20 items never stress the FIFO. test\_random failed with hundreds of data mismatches, the first once the FIFO started filling up and wrapping around.



\*\*Bug 2: wrong full check.\*\* I changed the full comparison so it used the raw synchronized read pointer and not the corrected one. Both tests failed with a simulation timeout, because the FIFO stopped making progress. This is why every test has a timeout.



Lesson: a directed test alone missed Bug 1. Random traffic with coverage found it.



\## Run it



Run `make` in this folder. Needs Python, cocotb 2.x, Icarus Verilog and make.

