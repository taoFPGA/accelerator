// ===========================================================================
// Matrix.h -- fixed-point matrix container + CPU/FPGA matmul entry points
//
// Matrix owns a heap buffer padded on both axes up to a multiple of A_SIZE
// (the systolic tile edge), so the accelerator always sees whole tiles;
// `rows`/`cols` are the logical size, `real_rows`/`real_cols` the padded
// size, and element (r,c) lives at base_addr[r*real_cols + c].
//
//   Matrix_mul_soft  -- reference A*B=C on the CPU (int accumulate, optional
//                       round-half-up right shift by R_shift, saturate int8).
//   Matrix_mul_hard  -- same result via the FPGA: cache-flush the buffers,
//                       program the accelerator's control regs + 3 AXI-DMA
//                       channels, poll the S2MM channel for done.
//   Matrix_compare   -- byte-compare two Matrix buffers.
// See Matrix.cpp for the implementations and Defines.h for the address map.
// ===========================================================================
#ifndef MY_MATRIX_H
#define MY_MATRIX_H
#include "xil_types.h"
#include "Defines.h"

class Matrix {
private:
    int real_cols;
    int real_rows;
    int real_size;
    DATA_TYPE * base_addr;

public:
    int rows;
    int cols;
    // constructor
    Matrix(int rows, int cols);

    // destructor
    ~Matrix();

    int get_real_cols() const;
    int get_real_rows() const;
    int get_real_size() const;
    DATA_TYPE* get_base_addr() const;
    void set_value(int row, int col, DATA_TYPE value);
    DATA_TYPE get_value(int row, int col);
    void mat_print();

};
void Matrix_mul_soft(Matrix &A, Matrix &B, Matrix &C, int R_shift); //A*B=C
void Matrix_mul_hard(Matrix &A, Matrix &B, Matrix &C, int R_shift); //A*B=C
bool  Matrix_compare(const Matrix &A, const Matrix &B);
#endif
