// Asynchronous FIFO: write clock and read clock are different.
// Pointers cross between clock domains in Gray code.
module async_fifo #(
    parameter DSIZE = 8,
    parameter ASIZE = 4          // depth = 2**ASIZE = 16
)(
    // write side
    input  wire              wclk,
    input  wire              wrst_n,
    input  wire              winc,
    input  wire [DSIZE-1:0]  wdata,
    output reg               wfull,
    // read side
    input  wire              rclk,
    input  wire              rrst_n,
    input  wire              rinc,
    output wire [DSIZE-1:0]  rdata,
    output reg               rempty
);

    reg [DSIZE-1:0] mem [0:(1<<ASIZE)-1];

    // binary and Gray pointers (one extra bit to tell full from empty)
    reg [ASIZE:0] wbin, wptr;
    reg [ASIZE:0] rbin, rptr;

    // two-flop synchronizers: the other side's Gray pointer
    reg [ASIZE:0] wq1_rptr, wq2_rptr;
    reg [ASIZE:0] rq1_wptr, rq2_wptr;

    // ---------------- write side ----------------
    wire [ASIZE:0] wbin_next  = wbin + (winc & ~wfull);
    wire [ASIZE:0] wgray_next = (wbin_next >> 1) ^ wbin_next;

    wire wfull_val = (wgray_next ==
                     {~wq2_rptr[ASIZE:ASIZE-1], wq2_rptr[ASIZE-2:0]});

    always @(posedge wclk) begin
        if (winc && !wfull)
            mem[wbin[ASIZE-1:0]] <= wdata;
    end

    always @(posedge wclk or negedge wrst_n) begin
        if (!wrst_n) begin
            wbin  <= 0;
            wptr  <= 0;
            wfull <= 1'b0;
        end else begin
            wbin  <= wbin_next;
            wptr  <= wgray_next;
            wfull <= wfull_val;
        end
    end

    // read pointer synchronized into the write clock domain
    always @(posedge wclk or negedge wrst_n) begin
        if (!wrst_n) begin
            wq1_rptr <= 0;
            wq2_rptr <= 0;
        end else begin
            wq1_rptr <= rptr;
            wq2_rptr <= wq1_rptr;
        end
    end

    // ---------------- read side ----------------
    wire [ASIZE:0] rbin_next  = rbin + (rinc & ~rempty);
    wire [ASIZE:0] rgray_next = (rbin_next >> 1) ^ rbin_next;

    wire rempty_val = (rgray_next == rq2_wptr);

    assign rdata = mem[rbin[ASIZE-1:0]];

    always @(posedge rclk or negedge rrst_n) begin
        if (!rrst_n) begin
            rbin   <= 0;
            rptr   <= 0;
            rempty <= 1'b1;
        end else begin
            rbin   <= rbin_next;
            rptr   <= rgray_next;
            rempty <= rempty_val;
        end
    end

    // write pointer synchronized into the read clock domain
    always @(posedge rclk or negedge rrst_n) begin
        if (!rrst_n) begin
            rq1_wptr <= 0;
            rq2_wptr <= 0;
        end else begin
            rq1_wptr <= wptr;
            rq2_wptr <= rq1_wptr;
        end
    end

endmodule