// ===========================================================================
// main.cpp -- bare-metal Zynq PS self-test for the MatMul accelerator
//
// Runs on the Cortex-A9 (no OS) as a Vitis/SDK "application project". It
//   1. builds two random int8 matrices A (IN_ROWS x IN_COLS) and
//      B (IN_COLS x OUT_COLS), zero-padded up to a multiple of A_SIZE by
//      the Matrix class;
//   2. computes C  = A*B on the CPU            (Matrix_mul_soft);
//   3. computes C_hard = A*B on the FPGA       (Matrix_mul_hard -- drives the
//      three AXI-DMA channels and the accelerator's control registers, see
//      Matrix.cpp);
//   4. memcmp's the two and prints "Right!" / "Wrong!".
//
// This is the C++ counterpart of the Python driver in apps/MM.py (which does
// the same thing from PYNQ instead of bare metal). Address map and DMA
// register offsets are in Defines.h.
// ===========================================================================
#include "Matrix.h"
#include "stdio.h"
#include <stdlib.h>
int main(){
	// Deliberately non-multiples of A_SIZE (16) to exercise the padding path.
	u32 IN_ROWS_NUM = 121;
	u32 IN_COLS_NUM = 311;
	u32 OUT_COLS_NUM = 72;

	int R_shift = 0;

    u32 i;
    u32 j;
    Matrix A(IN_ROWS_NUM, IN_COLS_NUM);
    Matrix B(IN_COLS_NUM, OUT_COLS_NUM);
    Matrix C(IN_ROWS_NUM, OUT_COLS_NUM);
    Matrix C_hard(IN_ROWS_NUM, OUT_COLS_NUM);
	for(i=0;i<IN_ROWS_NUM;i++){
		for(j=0;j<IN_COLS_NUM;j++){
			DATA_TYPE value = rand()%256-128;//rand()%16-7;
//			DATA_TYPE value = (i * A_SIZE +j + 128)%256 - 128;
//			DATA_TYPE value = 1;
			A.set_value(i,j,value);
		}
	}

	for(i=0;i<IN_COLS_NUM;i++){
		for(j=0;j<OUT_COLS_NUM;j++){
			DATA_TYPE value = rand()%256-128;//rand()%16-7;
//			DATA_TYPE value = (i * A_SIZE +j + 128)%256 - 128;
//			DATA_TYPE value = 2;
			B.set_value(i,j,value);
		}
	}

	Matrix_mul_soft(A, B, C, R_shift);
	Matrix_mul_hard(A, B, C_hard, R_shift);
	bool result = Matrix_compare(C, C_hard);
	if(result){
		printf("Right!");
	}else{
		printf("Wrong!");
	}

	return 0;
}
