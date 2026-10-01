/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.c
  * @brief          : Main program body
  ******************************************************************************
  * @attention
  *
  * Copyright (c) 2026 STMicroelectronics.
  * All rights reserved.
  *
  * This software is licensed under terms that can be found in the LICENSE file
  * in the root directory of this software component.
  * If no LICENSE file comes with this software, it is provided AS-IS.
  *
  ******************************************************************************
  */
/* USER CODE END Header */
/* Includes ------------------------------------------------------------------*/
#include "main.h"
#include "cmsis_os.h"
#include "SEGGER_RTT.h"
#include <string.h>   // ADD THIS for strchr, atoi
#include <stdlib.h> 
#include <math.h>     // ADD THIS for logf, NAN, isnan
/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */

/* USER CODE END Includes */

/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN PTD */

/* USER CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */

/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */

/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/
ADC_HandleTypeDef hadc1;
ADC_HandleTypeDef hadc2;
DMA_HandleTypeDef hdma_adc1;
DMA_HandleTypeDef hdma_adc2;

CAN_HandleTypeDef hcan1;

I2C_HandleTypeDef hi2c1;

TIM_HandleTypeDef htim1;
TIM_HandleTypeDef htim3;
TIM_HandleTypeDef htim8; 
/* Definitions for defaultTask */
osThreadId_t defaultTaskHandle;
const osThreadAttr_t defaultTask_attributes = {
  .name = "defaultTask",
  .stack_size = 128 * 4,
  .priority = (osPriority_t) osPriorityNormal,
};
/* Definitions for CurrentSense */
osThreadId_t CurrentSenseHandle;
const osThreadAttr_t CurrentSense_attributes = {
  .name = "CurrentSense",
  .stack_size = 256 * 4,
  .priority = (osPriority_t) osPriorityHigh,
};
/* Definitions for PWM */
osThreadId_t PWMHandle;
const osThreadAttr_t PWM_attributes = {
  .name = "PWM",
  .stack_size = 128 * 4,
  .priority = (osPriority_t) osPriorityNormal,
};
/* Definitions for VoltageMonitor */
osThreadId_t VoltageMonitorHandle;
const osThreadAttr_t VoltageMonitor_attributes = {
  .name = "VoltageMonitor",
  .stack_size = 256 * 4,
  .priority = (osPriority_t) osPriorityNormal,
};
/* Definitions for Balancing_Bus_S */
osThreadId_t Balancing_Bus_SHandle;
const osThreadAttr_t Balancing_Bus_S_attributes = {
  .name = "Balancing_Bus_S",
  .stack_size = 128 * 4,
  .priority = (osPriority_t) osPriorityNormal,
};
/* Definitions for Temperature_Sen */
osThreadId_t Temperature_SenHandle;
const osThreadAttr_t Temperature_Sen_attributes = {
  .name = "Temperature_Sen",
  .stack_size = 128 * 4,
  .priority = (osPriority_t) osPriorityLow,
};
/* USER CODE BEGIN PV */
// PWM control variables (mirrors main OLD.c)
volatile uint32_t pwm_frequency  = 71000;
volatile uint8_t  pwm_duty_ch1   = 0;
volatile uint8_t  pwm_duty_ch2   = 0;
volatile uint8_t  pwm_duty_ch3   = 0;
volatile uint8_t  pwm_duty_ch4   = 40;
volatile uint8_t  pwm_enabled    = 0;

#define RTT_COMMAND_BUFFER_SIZE  32

// RTT command handling
volatile uint8_t command_received = 0;
volatile char rtt_command[RTT_COMMAND_BUFFER_SIZE] = {0};
static int rtt_cmd_index = 0;

// Switch state bitmask
// Bit layout per cell (4 bits per cell):
//   bit0 = MT, bit1 = MB_POS, bit2 = MB_NEG, (bit3 spare)
// Cell N bits start at (N-1)*4
volatile uint16_t switch_state = 0;

volatile uint16_t adc_raw[4] = {0};   // DMA writes here
volatile uint16_t adc_ch0 = 0;
volatile uint16_t adc_ch1 = 0;
volatile uint16_t adc_ch2 = 0;
volatile uint16_t adc_ch3 = 0;

/* ===== ADC1 -> Current (mA) conversion =====
   TODO: recalibrate ADC_OFFSET_CHx for YOUR hardware: with zero current
   flowing, read the raw ADC1 counts printed on the target and put those
   values here. DIVIDER_GAIN and SENSITIVITY depend on your
   voltage divider and current sensor (values below are placeholders carried
   over from a previous ACS712-20A design: 100 mV/A, (33k+47k)/47k divider). */

/* Set to 1 to stream RAW, uncorrected ADC1 counts on the "ADC:" line for
   calibration. Set back to 0 to stream filtered current in mA once
   ADC_OFFSET_CH0..CH3 (and DIVIDER_GAIN / SENSITIVITY, if needed) are
   dialled in for this board. */
#define ADC_STREAM_RAW_FOR_CALIBRATION  0

/* Default zero-current offsets (counts, float), used at boot.
   Re-derived from a zero-current log: previous offsets + mean_mA / 13.717.
     CH0 1880 + 46.1 mA   -> 1883.36
     CH1 1866 + 73.5 mA   -> 1871.36
     CH2 1869 + 19.2 mA   -> 1870.40
     CH3 1867 + 102.2 mA  -> 1874.45
   The zero point of these sensors moves by several counts between power-ups,
   so send 'Z' from the GUI console with NO current flowing to re-measure them
   over ~2 s (or set ADC_AUTOZERO_AT_BOOT to 1). */
#define ADC_OFFSET_CH0  1883.36f
#define ADC_OFFSET_CH1  1871.36f
#define ADC_OFFSET_CH2  1870.40f
#define ADC_OFFSET_CH3  1874.45f

/* Block averaging: the DMA ISR ACCUMULATES every conversion (TIM3 = 5 kHz)
   and hands CurrentSense the sum of ADC_BLOCK_N of them. 100 conversions =
   20 ms = exactly one 50 Hz mains cycle, so 50/100/150... Hz pickup averages
   out instead of being aliased into slow wander by 1-in-100 sampling. */
#define ADC_BLOCK_N          100
#define ADC_ZERO_BLOCKS      100   /* 'Z' command: 100 blocks = 2 s          */
#define ADC_AUTOZERO_AT_BOOT 0     /* 1 = zero automatically at power-up     */

/* Zero-current offsets actually in use. Float, so an averaged fractional
   count is kept. Only the CurrentSense task writes these. */
static float adc_offset[4] = { ADC_OFFSET_CH0, ADC_OFFSET_CH1,
                               ADC_OFFSET_CH2, ADC_OFFSET_CH3 };

#define ADC_BITS      4095.0f
#define V_REF         3.3f
#define DIVIDER_GAIN  1.70212766f   /* (33k + 47k) / 47k          */
#define SENSITIVITY   0.100f        /* V/A, e.g. 100 mV/A sensor  */

/* One EMA on the 50 Hz block means (tau ~ 0.2 s). Float state, so there is
   no integer-truncation dead-band. */
#define FILTER_ALPHA  0.10f

/* Sums of ADC_BLOCK_N conversions per channel, written by the DMA ISR */
volatile uint32_t adc1_block_sum[4] = {0};
/* Set by the 'Z' command, consumed by the CurrentSense task */
volatile uint8_t  adc_zero_request = 0;

/* Filtered current in mA - this is what gets sent to the GUI */
volatile int16_t current_mA_ch0 = 0;
volatile int16_t current_mA_ch1 = 0;
volatile int16_t current_mA_ch2 = 0;
volatile int16_t current_mA_ch3 = 0;

// RTOS semaphore for ADC-ready signalling
osSemaphoreId_t adcDoneSem = NULL;

/* Multiple tasks (CurrentSense, VoltageMonitor, Temperature_Sen, the
   command task) all print to the same RTT buffer. SEGGER_RTT_printf is
   NOT re-entrant across tasks by itself, so without a mutex a higher
   priority task can preempt another mid-write and interleave its bytes
   into the buffer -- that's what produces garbled/binary-looking output
   on the host console. Every print goes through RTT_PRINTF() below,
   which takes rttMutex first. */
osMutexId_t rttMutex = NULL;
#define RTT_PRINTF(...) do { \
    if (rttMutex) osMutexAcquire(rttMutex, osWaitForever); \
    SEGGER_RTT_printf(0, __VA_ARGS__); \
    if (rttMutex) osMutexRelease(rttMutex); \
} while (0)

// ===== ADC2 raw capture =====
volatile uint16_t adc2_raw[4] = {0};
volatile uint16_t adc2_ch0 = 0;
volatile uint16_t adc2_ch1 = 0;
volatile uint16_t adc2_ch2 = 0;
volatile uint16_t adc2_ch3 = 0;

// RTOS semaphore for ADC2-ready signalling
osSemaphoreId_t adc2DoneSem = NULL;
/* ===== Temperature EMA filter state (per channel) =====
   Stored as tenths of °C × 16 (fixed point) to avoid float in the loop.
   Alpha = 1/8 gives a nice smoothing without much lag at 10 Hz. */
#define TEMP_FILTER_SHIFT   10        /* alpha = 1/(2^3) = 1/8 */
static int32_t temp_ema_x16[4] = {0, 0, 0, 0};
static uint8_t temp_ema_primed[4] = {0, 0, 0, 0};
/* ===== BQ76907 BMS IC ===== */
#define BQ76907_I2C_ADDR        (0x08 << 1)

#define CMD_SAFETY_STATUS_A     0x03
#define CMD_BATTERY_STATUS      0x12
#define CMD_CELL1_VOLTAGE       0x14
#define CMD_CELL2_VOLTAGE       0x18
#define CMD_CELL3_VOLTAGE       0x1C
#define CMD_CELL4_VOLTAGE       0x20
#define CMD_STACK_VOLTAGE       0x26

volatile int16_t  bq_cell1_mv = 0;
volatile int16_t  bq_cell2_mv = 0;
volatile int16_t  bq_cell3_mv = 0;
volatile int16_t  bq_cell4_mv = 0;
volatile uint16_t bq_stack_mv = 0;
volatile uint16_t bq_battery_status = 0;
volatile uint8_t  bq_read_ok = 0;


/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
static void MX_GPIO_Init(void);
static void MX_DMA_Init(void);
static void MX_ADC1_Init(void);
static void MX_CAN1_Init(void);
static void MX_I2C1_Init(void);
static void MX_TIM1_Init(void);
static void MX_ADC2_Init(void);
static void MX_TIM3_Init(void);
static void MX_TIM8_Init(void);   // <-- ADD
void StartDefaultTask(void *argument);
void StartTask02(void *argument);
void StartTask03(void *argument);
void StartTask04(void *argument);
void StartTask05(void *argument);
void StartTask06(void *argument);

/* USER CODE BEGIN PFP */
void TIM1_SetDuty(uint8_t channel, uint8_t duty_percent);
void TIM1_SetAllDuties(uint8_t d1, uint8_t d2, uint8_t d3, uint8_t d4);
void TIM1_SetFrequency(uint32_t frequency_hz);
void update_pwm_outputs(void);
void process_rtt_command(void);
void RTT_ReadCommand(void);
void set_switch(uint8_t cell, const char *type, uint8_t state);
void print_help(void);
void print_state(void);

static HAL_StatusTypeDef BQ76907_ReadWord(uint8_t reg, uint16_t *out_raw);
static HAL_StatusTypeDef BQ76907_ReadS16(uint8_t reg, int16_t *out);
static HAL_StatusTypeDef BQ76907_ReadU16(uint8_t reg, uint16_t *out);
static uint8_t BQ76907_ReadAll(void);

static float adc_counts_to_mA(float counts_from_zero);
/* USER CODE END PFP */

/* Private user code ---------------------------------------------------------*/
/* USER CODE BEGIN 0 */
static HAL_StatusTypeDef BQ76907_ReadWord(uint8_t reg, uint16_t *out_raw)
{
    uint8_t rx[2] = {0};
    HAL_StatusTypeDef ret = HAL_I2C_Mem_Read(&hi2c1, BQ76907_I2C_ADDR,
                                             reg, I2C_MEMADD_SIZE_8BIT,
                                             rx, 2, 20);   /* 20 ms, not 100 */
    if (ret != HAL_OK) return ret;
    *out_raw = (uint16_t)((uint16_t)rx[0] | ((uint16_t)rx[1] << 8));
    return HAL_OK;
}

static HAL_StatusTypeDef BQ76907_ReadS16(uint8_t reg, int16_t *out)
{
    uint16_t raw;
    HAL_StatusTypeDef ret = BQ76907_ReadWord(reg, &raw);
    if (ret == HAL_OK) *out = (int16_t)raw;
    return ret;
}

static HAL_StatusTypeDef BQ76907_ReadU16(uint8_t reg, uint16_t *out)
{
    return BQ76907_ReadWord(reg, out);
}

static uint8_t BQ76907_ReadAll(void)
{
    int16_t  c1=0, c2=0, c3=0, c4=0;
    uint16_t stack=0, batt_stat=0;
    uint8_t ok = 1;

    if (BQ76907_ReadS16(CMD_CELL1_VOLTAGE, &c1) != HAL_OK) ok = 0;
    if (BQ76907_ReadS16(CMD_CELL2_VOLTAGE, &c2) != HAL_OK) ok = 0;
    if (BQ76907_ReadS16(CMD_CELL3_VOLTAGE, &c3) != HAL_OK) ok = 0;
    if (BQ76907_ReadS16(CMD_CELL4_VOLTAGE, &c4) != HAL_OK) ok = 0;
    if (BQ76907_ReadU16(CMD_STACK_VOLTAGE,   &stack)     != HAL_OK) ok = 0;
    if (BQ76907_ReadU16(CMD_BATTERY_STATUS,  &batt_stat) != HAL_OK) ok = 0;

    if (ok) {
        bq_cell1_mv = c1; bq_cell2_mv = c2;
        bq_cell3_mv = c3; bq_cell4_mv = c4;
        bq_stack_mv = stack;
        bq_battery_status = batt_stat;
        bq_read_ok = 1;
    } else {
        bq_read_ok = 0;
    }
    return ok;
}
/* ===== ADC1 -> Current (mA) helper ===== */

/**
 * @brief  Convert ADC1 counts relative to the zero-current offset (centred
 *         on 0) into signed current in mA.
 *         Same formula as the old adc_to_current_mA_simple(); it takes and
 *         returns float so the fractional counts left by block averaging are
 *         not rounded away (1 count = ~13.7 mA with these constants).
 */
static float adc_counts_to_mA(float counts_from_zero)
{
    float v_adc     = (counts_from_zero / ADC_BITS) * V_REF;
    float v_sensor  = v_adc * DIVIDER_GAIN;
    float current_A = v_sensor / SENSITIVITY;
    return current_A * 1000.0f;
}

/**
 * @brief  Set a specific switch for a cell.
 * @param  cell: 1..4
 * @param  type: "MT", "MB" (positive bus), "NEG" (negative bus)
 * @param  state: 0 = OFF, 1 = ON
 * @retval None
 */
void set_switch(uint8_t cell, const char *type, uint8_t state)
{
    if (cell < 1 || cell > 4) return;

    int on = (state != 0);
    int bit_pos = (cell - 1) * 4;
    int bit = -1;

    if (strcmp(type, "MT") == 0) {
        bit = bit_pos + 0;
        switch (cell) {
            case 1: on ? MT1_ON()      : MT1_OFF();      break;
            case 2: on ? MT2_ON()      : MT2_OFF();      break;
            case 3: on ? MT3_ON()      : MT3_OFF();      break;
            case 4: on ? MT4_ON()      : MT4_OFF();      break;
        }
    } else if (strcmp(type, "MB") == 0) {
        bit = bit_pos + 1;
        switch (cell) {
            case 1: on ? MB1B_POS_ON() : MB1B_POS_OFF(); break;
            case 2: on ? MB2B_POS_ON() : MB2B_POS_OFF(); break;
            case 3: on ? MB3B_POS_ON() : MB3B_POS_OFF(); break;
            case 4: on ? MB4B_POS_ON() : MB4B_POS_OFF(); break;
        }
    } else if (strcmp(type, "NEG") == 0) {
        bit = bit_pos + 2;
        switch (cell) {
            case 1: on ? MB1B_NEG_ON() : MB1B_NEG_OFF(); break;
            case 2: on ? MB2B_NEG_ON() : MB2B_NEG_OFF(); break;
            case 3: on ? MB3B_NEG_ON() : MB3B_NEG_OFF(); break;
            case 4: on ? MB4B_NEG_ON() : MB4B_NEG_OFF(); break;
        }
    } else {
        RTT_PRINTF("ERR: Unknown switch type '%s' (use MT, MB, NEG)\r\n", type);
        return;
    }

    if (bit >= 0) {
        if (on) switch_state |=  (1u << bit);
        else    switch_state &= ~(1u << bit);
    }

    RTT_PRINTF("OK: Cell%d %s %s\r\n", cell, type, on ? "ON" : "OFF");
    RTT_PRINTF("STATE:0x%04X\r\n", switch_state);
}

/**
 * @brief  Process a completed command line.
 *         Formats:
 *           S<cell><type>=<0|1>   e.g. S1MT=1  S2NEG=0
 *           A<cell>=<0|1>         all three switches of a cell
 *           ?                     help
 *           Q                     query state
 */

static inline uint16_t duty_to_compare(uint8_t duty_percent, uint16_t period)
{
    if (duty_percent >= 100) return period;
    if (duty_percent == 0)   return 0;
    return (uint16_t)((uint32_t)duty_percent * period / 100);
}

void TIM1_SetDuty(uint8_t channel, uint8_t duty_percent)
{
    uint16_t period  = __HAL_TIM_GET_AUTORELOAD(&htim1);
    uint16_t compare = duty_to_compare(duty_percent, period);
    switch (channel) {
        case 1: __HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_1, compare); break;
        case 2: __HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_2, compare); break;
        case 3: __HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_3, compare); break;
        case 4: __HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_4, compare); break;
        default: break;
    }
}

void TIM1_SetAllDuties(uint8_t d1, uint8_t d2, uint8_t d3, uint8_t d4)
{
    uint16_t period = __HAL_TIM_GET_AUTORELOAD(&htim1);
    __HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_1, duty_to_compare(d1, period));
    __HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_2, duty_to_compare(d2, period));
    __HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_3, duty_to_compare(d3, period));
    __HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_4, duty_to_compare(d4, period));
}

void TIM1_SetFrequency(uint32_t frequency_hz)
{
    uint32_t apb2_clock = 168000000;
    uint32_t period = (apb2_clock / frequency_hz) - 1;
    if (period > 65535) period = 65535;
    if (period < 1)     period = 1;

    // Preserve current duty percentages across the period change
    uint16_t cur = __HAL_TIM_GET_AUTORELOAD(&htim1);
    uint8_t d1 = (cur ? (__HAL_TIM_GET_COMPARE(&htim1, TIM_CHANNEL_1) * 100) / cur : 0);
    uint8_t d2 = (cur ? (__HAL_TIM_GET_COMPARE(&htim1, TIM_CHANNEL_2) * 100) / cur : 0);
    uint8_t d3 = (cur ? (__HAL_TIM_GET_COMPARE(&htim1, TIM_CHANNEL_3) * 100) / cur : 0);
    uint8_t d4 = (cur ? (__HAL_TIM_GET_COMPARE(&htim1, TIM_CHANNEL_4) * 100) / cur : 0);

    HAL_TIM_PWM_Stop(&htim1, TIM_CHANNEL_1);
    HAL_TIM_PWM_Stop(&htim1, TIM_CHANNEL_2);
    HAL_TIM_PWM_Stop(&htim1, TIM_CHANNEL_3);
    HAL_TIM_PWM_Stop(&htim1, TIM_CHANNEL_4);

    __HAL_TIM_SET_AUTORELOAD(&htim1, period);
    __HAL_TIM_SET_COUNTER(&htim1, 0);
    TIM1_SetAllDuties(d1, d2, d3, d4);

    HAL_TIM_PWM_Start(&htim1, TIM_CHANNEL_1);
    HAL_TIM_PWM_Start(&htim1, TIM_CHANNEL_2);
    HAL_TIM_PWM_Start(&htim1, TIM_CHANNEL_3);
    HAL_TIM_PWM_Start(&htim1, TIM_CHANNEL_4);
}

void update_pwm_outputs(void)
{
    if (pwm_enabled) {
        TIM1_SetAllDuties(pwm_duty_ch1, pwm_duty_ch2, pwm_duty_ch3, pwm_duty_ch4);
    }
}

void process_rtt_command(void)
{
    if (!command_received) return;
    command_received = 0;

    char cmd_buf[RTT_COMMAND_BUFFER_SIZE];
    strncpy(cmd_buf, (char *)rtt_command, RTT_COMMAND_BUFFER_SIZE - 1);
    cmd_buf[RTT_COMMAND_BUFFER_SIZE - 1] = '\0';

    // Trim leading spaces
    char *p = cmd_buf;
    while (*p == ' ' || *p == '\t') p++;
    if (*p == '\0') return;

    char cmd = *p;

    if (cmd == '?') {
        print_help();
        return;
    }
    if (cmd == 'Q' || cmd == 'q') {
        print_state();
        return;
    }

    if (cmd == 'S' || cmd == 's') {
        // S<cell><TYPE>=<val>    TYPE = MT | MB | NEG
        if (p[1] < '1' || p[1] > '4') {
            RTT_PRINTF("ERR: bad cell (must be 1-4)\r\n");
            return;
        }
        uint8_t cell = p[1] - '0';

        char *eq = strchr(p, '=');
        if (!eq) {
            RTT_PRINTF("ERR: missing '='\r\n");
            return;
        }

        // Extract type between p+2 and eq
        char type[8] = {0};
        int len = (int)(eq - (p + 2));
        if (len <= 0 || len >= (int)sizeof(type)) {
            RTT_PRINTF("ERR: bad switch type\r\n");
            return;
        }
        strncpy(type, p + 2, len);
        type[len] = '\0';

        int value = atoi(eq + 1);
        set_switch(cell, type, (uint8_t)(value != 0));
        return;
    }

    if (cmd == 'A' || cmd == 'a') {
        // A<cell>=<val>  -> all three switches of that cell
        if (p[1] < '1' || p[1] > '4') {
            RTT_PRINTF("ERR: bad cell (must be 1-4)\r\n");
            return;
        }
        char *eq = strchr(p, '=');
        if (!eq) {
            RTT_PRINTF("ERR: missing '='\r\n");
            return;
        }
        uint8_t cell = p[1] - '0';
        uint8_t v = (uint8_t)(atoi(eq + 1) != 0);
        set_switch(cell, "MT",  v);
        set_switch(cell, "MB",  v);
        set_switch(cell, "NEG", v);
        return;
    }
        if (cmd == 'F' || cmd == 'f') {
        // F<freq>   e.g. F71000
        int freq = atoi(p + 1);
        if (freq >= 100 && freq <= 168000) {
            pwm_frequency = (uint32_t)freq;
            TIM1_SetFrequency(pwm_frequency);
            RTT_PRINTF("OK: Frequency set to %lu Hz\r\n",
                              (unsigned long)pwm_frequency);
        } else {
            RTT_PRINTF("ERR: frequency out of range (100-168000)\r\n");
        }
        return;
    }

    if (cmd == 'D' || cmd == 'd') {
        // D<ch>=<duty>   e.g. D1=50
        if (p[1] < '1' || p[1] > '4') {
            RTT_PRINTF("ERR: bad channel (1-4)\r\n");
            return;
        }
        char *eq = strchr(p, '=');
        if (!eq) {
            RTT_PRINTF("ERR: missing '='\r\n");
            return;
        }
        int ch  = p[1] - '0';
        int val = atoi(eq + 1);
        if (val < 0 || val > 100) {
            RTT_PRINTF("ERR: duty out of range (0-100)\r\n");
            return;
        }
        switch (ch) {
            case 1: pwm_duty_ch1 = val; break;
            case 2: pwm_duty_ch2 = val; break;
            case 3: pwm_duty_ch3 = val; break;
            case 4: pwm_duty_ch4 = val; break;
        }
        if (pwm_enabled) update_pwm_outputs();
        RTT_PRINTF("OK: CH%d duty set to %d%%\r\n", ch, val);
        return;
    }

    if (cmd == 'P' || cmd == 'p') {
        // P=<0|1>
        char *eq = strchr(p, '=');
        int val = eq ? atoi(eq + 1) : atoi(p + 1);
        if (val == 1) {
            pwm_enabled = 1;
            update_pwm_outputs();
            HAL_TIM_PWM_Start(&htim1, TIM_CHANNEL_1);
            HAL_TIM_PWM_Start(&htim1, TIM_CHANNEL_2);
            HAL_TIM_PWM_Start(&htim1, TIM_CHANNEL_3);
            HAL_TIM_PWM_Start(&htim1, TIM_CHANNEL_4);
            RTT_PRINTF("OK: PWM Enabled\r\n");
        } else if (val == 0) {
            pwm_enabled = 0;
            HAL_TIM_PWM_Stop(&htim1, TIM_CHANNEL_1);
            HAL_TIM_PWM_Stop(&htim1, TIM_CHANNEL_2);
            HAL_TIM_PWM_Stop(&htim1, TIM_CHANNEL_3);
            HAL_TIM_PWM_Stop(&htim1, TIM_CHANNEL_4);
            RTT_PRINTF("OK: PWM Disabled\r\n");
        } else {
            RTT_PRINTF("ERR: PWM state must be 0 or 1\r\n");
        }
        return;
    }

    if (cmd == 'Z' || cmd == 'z') {
        // Z  -> re-measure ADC1 zero-current offsets (NO current must flow)
        adc_zero_request = 1;
        RTT_PRINTF("OK: zeroing ADC1 (keep current at 0 A, ~2 s)\r\n");
        return;
    }

    RTT_PRINTF("ERR: unknown command '%c' (send '?' for help)\r\n", cmd);
}

/**
 * @brief  Poll the RTT down-buffer and accumulate chars into a line.
 */
void RTT_ReadCommand(void)
{
    while (SEGGER_RTT_HasKey()) {
        char ch = (char)SEGGER_RTT_GetKey();

        if (ch == '\r' || ch == '\n') {
            if (rtt_cmd_index > 0) {
                rtt_command[rtt_cmd_index] = '\0';
                command_received = 1;
                rtt_cmd_index = 0;
            }
        } else if (ch == '\b' || ch == 0x7F) {
            if (rtt_cmd_index > 0) rtt_cmd_index--;
        } else if (rtt_cmd_index < RTT_COMMAND_BUFFER_SIZE - 1) {
            rtt_command[rtt_cmd_index++] = ch;
            if (rttMutex) osMutexAcquire(rttMutex, osWaitForever);
            SEGGER_RTT_Write(0, &ch, 1);   // local echo
            if (rttMutex) osMutexRelease(rttMutex);
        }
    }
}

void print_help(void)
{
    RTT_PRINTF("\r\n=== Commands ===\r\n");
    RTT_PRINTF("  S<cell><TYPE>=<0|1>   Set one switch\r\n");
    RTT_PRINTF("      cell = 1..4\r\n");
    RTT_PRINTF("      TYPE = MT | MB | NEG\r\n");
    RTT_PRINTF("      ex: S1MT=1   S2MB=0   S4NEG=1\r\n");
    RTT_PRINTF("  A<cell>=<0|1>        Set MT+MB+NEG together\r\n");
    RTT_PRINTF("  Q                    Query current state\r\n");
    RTT_PRINTF("  ?                    This help\r\n");
    RTT_PRINTF("  F<freq>            Set PWM frequency (100-168000 Hz)\r\n");
    RTT_PRINTF("  D<ch>=<0-100>      Set PWM duty on channel 1..4\r\n");
    RTT_PRINTF("  P=<0|1>            Master PWM enable/disable\r\n");
    RTT_PRINTF("  Z                  Re-zero ADC1 current offsets (0 A!)\r\n");
    RTT_PRINTF("=========================\r\n\r\n");
}

void print_state(void)
{
    RTT_PRINTF("STATE:0x%04X\r\n", switch_state);
    for (uint8_t c = 1; c <= 4; c++) {
        int b = (c - 1) * 4;
        RTT_PRINTF("  Cell%d: MT=%d MB=%d NEG=%d\r\n",
                          c,
                          (switch_state >> (b + 0)) & 1,
                          (switch_state >> (b + 1)) & 1,
                          (switch_state >> (b + 2)) & 1);
        RTT_PRINTF("  PWM: %s  freq=%lu Hz  d1=%d d2=%d d3=%d d4=%d\r\n",
                          pwm_enabled ? "ON" : "OFF",
                          (unsigned long)pwm_frequency,
                          pwm_duty_ch1, pwm_duty_ch2, pwm_duty_ch3, pwm_duty_ch4);                  
    }
}

/* USER CODE END 0 */
/* USER CODE BEGIN Temperature conversion */

/* Thermistor lookup table: temperature (°C, int16) and resistance (ohms, uint32) */
typedef struct {
    int16_t  temp_c;
    uint32_t res_ohm;
} ThermistorPoint;

/* Sorted by temperature ascending (matches your table) */
static const ThermistorPoint therm_table[] = {
    {-30, 1790000}, {-25, 1321000}, {-20,  984700}, {-15,  740800},
    {-10,  562300}, { -5,  430500}, {  0,  332300}, {  5,  257500},
    { 10,  201100}, { 15,  158200}, { 20,  125400}, { 25,  100000},
    { 30,   80290}, { 35,   64870}, { 40,   57720}, { 45,   43100},
    { 50,   35420}, { 55,   29260}, { 60,   24300}, { 65,   20270},
    { 70,   16990}, { 75,   14310}, { 80,   12100}, { 85,   10270},
    { 90,    8758}, { 95,    7495}, {100,    6438}, {105,    5550},
    {110,    4801},
};

#define THERM_TABLE_SIZE  (sizeof(therm_table) / sizeof(therm_table[0]))
#define THERM_R_FIXED     100000.0f      /* 100 kΩ series resistor   */
#define THERM_V_SUPPLY    3.3f           /* Supply voltage           */
#define ADC_FULL_SCALE    4095.0f        /* 12-bit ADC               */

/**
 * @brief  Convert a raw 12-bit ADC2 reading into temperature in °C.
 * @param  adc_raw  raw ADC value (0..4095)
 * @retval temperature in °C (float). Returns NAN for invalid input.
 */
static float adc_to_temperature_c(uint16_t adc_raw)
{
    /* Guard against shorted input / open circuit */
    if (adc_raw == 0 || adc_raw >= (uint16_t)ADC_FULL_SCALE) {
        return NAN;
    }

    /* Resistance of the thermistor (bottom of divider) */
    float r_therm = THERM_R_FIXED
                  * ((float)adc_raw / (ADC_FULL_SCALE - (float)adc_raw));

    /* Find the two table entries we sit between */
    if (r_therm >= (float)therm_table[0].res_ohm) {
        return (float)therm_table[0].temp_c;                 /* colder than -30 °C */
    }
    if (r_therm <= (float)therm_table[THERM_TABLE_SIZE-1].res_ohm) {
        return (float)therm_table[THERM_TABLE_SIZE-1].temp_c; /* hotter than 110 °C */
    }

    for (size_t i = 0; i < THERM_TABLE_SIZE - 1; i++) {
        float r_hi = (float)therm_table[i].res_ohm;      /* higher R, lower T */
        float r_lo = (float)therm_table[i+1].res_ohm;

        if (r_therm <= r_hi && r_therm >= r_lo) {
            /* Linear interpolation in log(R) space gives better accuracy.
               Use it if you can afford the math; otherwise plain linear is fine. */
            float log_r    = logf(r_therm);
            float log_r_hi = logf(r_hi);
            float log_r_lo = logf(r_lo);

            float frac = (log_r_hi - log_r) / (log_r_hi - log_r_lo);

            float t_hi = (float)therm_table[i].temp_c;
            float t_lo = (float)therm_table[i+1].temp_c;

            return t_hi + frac * (t_lo - t_hi);
        }
    }
    return NAN;   /* should never get here */
}

/* USER CODE END Temperature conversion */
/**
  * @brief  The application entry point.
  * @retval int
  */
int main(void)
{

  /* USER CODE BEGIN 1 */
  SCB->VTOR = FLASH_BASE;
  /* USER CODE END 1 */

  /* MCU Configuration--------------------------------------------------------*/

  /* Reset of all peripherals, Initializes the Flash interface and the Systick. */
  HAL_Init();

  SEGGER_RTT_Init();
  /* USER CODE BEGIN Init */

  /* USER CODE END Init */

  /* Configure the system clock */
  SystemClock_Config();

  /* USER CODE BEGIN SysInit */

  /* USER CODE END SysInit */

  /* Initialize all configured peripherals */
  MX_GPIO_Init();
  MX_DMA_Init();
  MX_ADC1_Init();
  MX_CAN1_Init();
  MX_I2C1_Init();
  MX_TIM1_Init();
  MX_ADC2_Init();
  MX_TIM3_Init();
  MX_TIM8_Init();
  /* USER CODE BEGIN 2 */
  
// Make sure all switches start OFF
  MT1_OFF(); MB1B_POS_OFF(); MB1B_NEG_OFF();
  MT2_OFF(); MB2B_POS_OFF(); MB2B_NEG_OFF();
  MT3_OFF(); MB3B_POS_OFF(); MB3B_NEG_OFF();
  MT4_OFF(); MB4B_POS_OFF(); MB4B_NEG_OFF();
  switch_state = 0;

  RTT_PRINTF("\r\n*** STM32 RTT GPIO Control ready ***\r\n");
  RTT_PRINTF("Type '?' + Enter for help\r\n");
  TIM1_SetFrequency(pwm_frequency);
  /* ---- ADC1 + DMA + TIM3 start ---- */
  if (HAL_ADC_Start_DMA(&hadc1, (uint32_t*)adc_raw, 4) != HAL_OK)
  {
    Error_Handler();
  }
  HAL_TIM_Base_Start(&htim3);

  /* ---- ADC2 + DMA + TIM8 start ---- */
  HAL_TIM_Base_Start(&htim8);              // <-- start TIM8 FIRST
  if (HAL_ADC_Start_DMA(&hadc2, (uint32_t*)adc2_raw, 4) != HAL_OK)
  {
    Error_Handler();
  }

  /* USER CODE END 2 */

  /* Init scheduler */
  osKernelInitialize();

  /* USER CODE BEGIN RTOS_MUTEX */
  /* add mutexes, ... */
  /* USER CODE END RTOS_MUTEX */

  /* USER CODE BEGIN RTOS_SEMAPHORES */
  adcDoneSem = osSemaphoreNew(1, 0, NULL);
  if (adcDoneSem == NULL) { Error_Handler(); }

  adc2DoneSem = osSemaphoreNew(1, 0, NULL);
  if (adc2DoneSem == NULL) { Error_Handler(); }

  rttMutex = osMutexNew(NULL);
  if (rttMutex == NULL) { Error_Handler(); }
  /* USER CODE END RTOS_SEMAPHORES */

  /* USER CODE BEGIN RTOS_TIMERS */
  /* start timers, add new ones, ... */
  /* USER CODE END RTOS_TIMERS */

  /* USER CODE BEGIN RTOS_QUEUES */
  /* add queues, ... */
  /* USER CODE END RTOS_QUEUES */

  /* Create the thread(s) */
  /* creation of defaultTask */
  defaultTaskHandle = osThreadNew(StartDefaultTask, NULL, &defaultTask_attributes);

  /* creation of CurrentSense */
  CurrentSenseHandle = osThreadNew(StartTask02, NULL, &CurrentSense_attributes);

  /* creation of PWM */
  PWMHandle = osThreadNew(StartTask03, NULL, &PWM_attributes);

  /* creation of VoltageMonitor */
  VoltageMonitorHandle = osThreadNew(StartTask04, NULL, &VoltageMonitor_attributes);

  /* creation of Balancing_Bus_S */
  Balancing_Bus_SHandle = osThreadNew(StartTask05, NULL, &Balancing_Bus_S_attributes);

  /* creation of Temperature_Sen */
  Temperature_SenHandle = osThreadNew(StartTask06, NULL, &Temperature_Sen_attributes);

  /* USER CODE BEGIN RTOS_THREADS */
  /* add threads, ... */
  /* USER CODE END RTOS_THREADS */

  /* USER CODE BEGIN RTOS_EVENTS */
  /* add events, ... */
  /* USER CODE END RTOS_EVENTS */

  /* Start scheduler */
  osKernelStart();

  /* We should never get here as control is now taken by the scheduler */

  /* Infinite loop */
  /* USER CODE BEGIN WHILE */
  while (1)
  {
    /* USER CODE END WHILE */

    /* USER CODE BEGIN 3 */
  }
  /* USER CODE END 3 */
}

/**
  * @brief System Clock Configuration
  * @retval None
  */
void SystemClock_Config(void)
{
  RCC_OscInitTypeDef RCC_OscInitStruct = {0};
  RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};

  /** Configure the main internal regulator output voltage
  */
  __HAL_RCC_PWR_CLK_ENABLE();
  __HAL_PWR_VOLTAGESCALING_CONFIG(PWR_REGULATOR_VOLTAGE_SCALE1);

  /** Initializes the RCC Oscillators according to the specified parameters
  * in the RCC_OscInitTypeDef structure.
  */
  RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSI;
  RCC_OscInitStruct.HSIState = RCC_HSI_ON;
  RCC_OscInitStruct.HSICalibrationValue = RCC_HSICALIBRATION_DEFAULT;
  RCC_OscInitStruct.PLL.PLLState = RCC_PLL_ON;
  RCC_OscInitStruct.PLL.PLLSource = RCC_PLLSOURCE_HSI;
  RCC_OscInitStruct.PLL.PLLM = 8;
  RCC_OscInitStruct.PLL.PLLN = 168;
  RCC_OscInitStruct.PLL.PLLP = RCC_PLLP_DIV2;
  RCC_OscInitStruct.PLL.PLLQ = 4;
  if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
  {
    Error_Handler();
  }

  /** Initializes the CPU, AHB and APB buses clocks
  */
  RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK|RCC_CLOCKTYPE_SYSCLK
                              |RCC_CLOCKTYPE_PCLK1|RCC_CLOCKTYPE_PCLK2;
  RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
  RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
  RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV4;
  RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV2;

  if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_5) != HAL_OK)
  {
    Error_Handler();
  }
}

/**
  * @brief ADC1 Initialization Function
  * @param None
  * @retval None
  */
static void MX_ADC1_Init(void)
{
  ADC_ChannelConfTypeDef sConfig = {0};

  hadc1.Instance = ADC1;
  hadc1.Init.ClockPrescaler = ADC_CLOCK_SYNC_PCLK_DIV4;
  hadc1.Init.Resolution = ADC_RESOLUTION_12B;
  hadc1.Init.ScanConvMode = ENABLE;
  hadc1.Init.ContinuousConvMode = DISABLE;
  hadc1.Init.DiscontinuousConvMode = DISABLE;
  hadc1.Init.ExternalTrigConvEdge = ADC_EXTERNALTRIGCONVEDGE_RISING;
  hadc1.Init.ExternalTrigConv = ADC_EXTERNALTRIGCONV_T3_TRGO;
  hadc1.Init.DataAlign = ADC_DATAALIGN_RIGHT;
  hadc1.Init.NbrOfConversion = 4;
  hadc1.Init.DMAContinuousRequests = ENABLE;              // <-- was DISABLE
  hadc1.Init.EOCSelection = ADC_EOC_SEQ_CONV;             // <-- was ADC_EOC_SINGLE_CONV
  if (HAL_ADC_Init(&hadc1) != HAL_OK)
  {
    Error_Handler();
  }

  sConfig.SamplingTime = ADC_SAMPLETIME_28CYCLES;         // <-- 28 cycles

  sConfig.Channel = ADC_CHANNEL_0;  sConfig.Rank = 1;
  if (HAL_ADC_ConfigChannel(&hadc1, &sConfig) != HAL_OK) Error_Handler();

  sConfig.Channel = ADC_CHANNEL_1;  sConfig.Rank = 2;
  if (HAL_ADC_ConfigChannel(&hadc1, &sConfig) != HAL_OK) Error_Handler();

  sConfig.Channel = ADC_CHANNEL_2;  sConfig.Rank = 3;
  if (HAL_ADC_ConfigChannel(&hadc1, &sConfig) != HAL_OK) Error_Handler();

  sConfig.Channel = ADC_CHANNEL_3;  sConfig.Rank = 4;
  if (HAL_ADC_ConfigChannel(&hadc1, &sConfig) != HAL_OK) Error_Handler();
}

/**
  * @brief ADC2 Initialization Function
  * @param None
  * @retval None
  */
static void MX_ADC2_Init(void)
{
  ADC_ChannelConfTypeDef sConfig = {0};

  hadc2.Instance = ADC2;
  hadc2.Init.ClockPrescaler = ADC_CLOCK_SYNC_PCLK_DIV4;
  hadc2.Init.Resolution = ADC_RESOLUTION_12B;
  hadc2.Init.ScanConvMode = ENABLE;
  hadc2.Init.ContinuousConvMode = DISABLE;
  hadc2.Init.DiscontinuousConvMode = DISABLE;
  hadc2.Init.ExternalTrigConvEdge = ADC_EXTERNALTRIGCONVEDGE_RISING;   // <-- was NONE
  hadc2.Init.ExternalTrigConv     = ADC_EXTERNALTRIGCONV_T8_TRGO;      // <-- was SOFTWARE_START
  hadc2.Init.DataAlign = ADC_DATAALIGN_RIGHT;
  hadc2.Init.NbrOfConversion = 4;
  hadc2.Init.DMAContinuousRequests = ENABLE;                            // <-- was DISABLE
  hadc2.Init.EOCSelection = ADC_EOC_SEQ_CONV;                           // <-- was ADC_EOC_SINGLE_CONV
  if (HAL_ADC_Init(&hadc2) != HAL_OK) Error_Handler();

  sConfig.SamplingTime = ADC_SAMPLETIME_28CYCLES;                       // <-- was 3 cycles

  sConfig.Channel = ADC_CHANNEL_4;  sConfig.Rank = 1;
  if (HAL_ADC_ConfigChannel(&hadc2, &sConfig) != HAL_OK) Error_Handler();

  sConfig.Channel = ADC_CHANNEL_5;  sConfig.Rank = 2;
  if (HAL_ADC_ConfigChannel(&hadc2, &sConfig) != HAL_OK) Error_Handler();

  sConfig.Channel = ADC_CHANNEL_6;  sConfig.Rank = 3;
  if (HAL_ADC_ConfigChannel(&hadc2, &sConfig) != HAL_OK) Error_Handler();

  sConfig.Channel = ADC_CHANNEL_7;  sConfig.Rank = 4;
  if (HAL_ADC_ConfigChannel(&hadc2, &sConfig) != HAL_OK) Error_Handler();
}
/**
  * @brief CAN1 Initialization Function
  * @param None
  * @retval None
  */
static void MX_CAN1_Init(void)
{

  /* USER CODE BEGIN CAN1_Init 0 */

  /* USER CODE END CAN1_Init 0 */

  /* USER CODE BEGIN CAN1_Init 1 */

  /* USER CODE END CAN1_Init 1 */
  hcan1.Instance = CAN1;
  hcan1.Init.Prescaler = 16;
  hcan1.Init.Mode = CAN_MODE_NORMAL;
  hcan1.Init.SyncJumpWidth = CAN_SJW_1TQ;
  hcan1.Init.TimeSeg1 = CAN_BS1_1TQ;
  hcan1.Init.TimeSeg2 = CAN_BS2_1TQ;
  hcan1.Init.TimeTriggeredMode = DISABLE;
  hcan1.Init.AutoBusOff = DISABLE;
  hcan1.Init.AutoWakeUp = DISABLE;
  hcan1.Init.AutoRetransmission = DISABLE;
  hcan1.Init.ReceiveFifoLocked = DISABLE;
  hcan1.Init.TransmitFifoPriority = DISABLE;
  if (HAL_CAN_Init(&hcan1) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN CAN1_Init 2 */

  /* USER CODE END CAN1_Init 2 */

}

/**
  * @brief I2C1 Initialization Function
  * @param None
  * @retval None
  */
static void MX_I2C1_Init(void)
{

  /* USER CODE BEGIN I2C1_Init 0 */

  /* USER CODE END I2C1_Init 0 */

  /* USER CODE BEGIN I2C1_Init 1 */

  /* USER CODE END I2C1_Init 1 */
  hi2c1.Instance = I2C1;
  hi2c1.Init.ClockSpeed = 100000;
  hi2c1.Init.DutyCycle = I2C_DUTYCYCLE_2;
  hi2c1.Init.OwnAddress1 = 0;
  hi2c1.Init.AddressingMode = I2C_ADDRESSINGMODE_7BIT;
  hi2c1.Init.DualAddressMode = I2C_DUALADDRESS_DISABLE;
  hi2c1.Init.OwnAddress2 = 0;
  hi2c1.Init.GeneralCallMode = I2C_GENERALCALL_DISABLE;
  hi2c1.Init.NoStretchMode = I2C_NOSTRETCH_DISABLE;
  if (HAL_I2C_Init(&hi2c1) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN I2C1_Init 2 */

  /* USER CODE END I2C1_Init 2 */

}

/**
  * @brief TIM1 Initialization Function
  * @param None
  * @retval None
  */
static void MX_TIM1_Init(void)
{

  /* USER CODE BEGIN TIM1_Init 0 */

  /* USER CODE END TIM1_Init 0 */

  TIM_MasterConfigTypeDef sMasterConfig = {0};
  TIM_OC_InitTypeDef sConfigOC = {0};
  TIM_BreakDeadTimeConfigTypeDef sBreakDeadTimeConfig = {0};

  /* USER CODE BEGIN TIM1_Init 1 */

  /* USER CODE END TIM1_Init 1 */
  htim1.Instance = TIM1;
  htim1.Init.Prescaler = 0;
  htim1.Init.CounterMode = TIM_COUNTERMODE_UP;
  htim1.Init.Period = 65535;
  htim1.Init.ClockDivision = TIM_CLOCKDIVISION_DIV1;
  htim1.Init.RepetitionCounter = 0;
  htim1.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_ENABLE;
  if (HAL_TIM_PWM_Init(&htim1) != HAL_OK)
  {
    Error_Handler();
  }
  sMasterConfig.MasterOutputTrigger = TIM_TRGO_RESET;
  sMasterConfig.MasterSlaveMode = TIM_MASTERSLAVEMODE_DISABLE;
  if (HAL_TIMEx_MasterConfigSynchronization(&htim1, &sMasterConfig) != HAL_OK)
  {
    Error_Handler();
  }
  sConfigOC.OCMode = TIM_OCMODE_PWM1;
  sConfigOC.Pulse = 0;
  sConfigOC.OCPolarity = TIM_OCPOLARITY_HIGH;
  sConfigOC.OCNPolarity = TIM_OCNPOLARITY_HIGH;
  sConfigOC.OCFastMode = TIM_OCFAST_DISABLE;
  sConfigOC.OCIdleState = TIM_OCIDLESTATE_RESET;
  sConfigOC.OCNIdleState = TIM_OCNIDLESTATE_RESET;
  if (HAL_TIM_PWM_ConfigChannel(&htim1, &sConfigOC, TIM_CHANNEL_1) != HAL_OK)
  {
    Error_Handler();
  }
  if (HAL_TIM_PWM_ConfigChannel(&htim1, &sConfigOC, TIM_CHANNEL_2) != HAL_OK)
  {
    Error_Handler();
  }
  if (HAL_TIM_PWM_ConfigChannel(&htim1, &sConfigOC, TIM_CHANNEL_3) != HAL_OK)
  {
    Error_Handler();
  }
  if (HAL_TIM_PWM_ConfigChannel(&htim1, &sConfigOC, TIM_CHANNEL_4) != HAL_OK)
  {
    Error_Handler();
  }
  sBreakDeadTimeConfig.OffStateRunMode = TIM_OSSR_DISABLE;
  sBreakDeadTimeConfig.OffStateIDLEMode = TIM_OSSI_DISABLE;
  sBreakDeadTimeConfig.LockLevel = TIM_LOCKLEVEL_OFF;
  sBreakDeadTimeConfig.DeadTime = 0;
  sBreakDeadTimeConfig.BreakState = TIM_BREAK_DISABLE;
  sBreakDeadTimeConfig.BreakPolarity = TIM_BREAKPOLARITY_HIGH;
  sBreakDeadTimeConfig.AutomaticOutput = TIM_AUTOMATICOUTPUT_DISABLE;
  if (HAL_TIMEx_ConfigBreakDeadTime(&htim1, &sBreakDeadTimeConfig) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN TIM1_Init 2 */

  /* USER CODE END TIM1_Init 2 */
  HAL_TIM_MspPostInit(&htim1);

}

/**
  * @brief TIM3 Initialization Function
  * @param None
  * @retval None
  */
static void MX_TIM3_Init(void)
{

  /* USER CODE BEGIN TIM3_Init 0 */

  /* USER CODE END TIM3_Init 0 */

  TIM_ClockConfigTypeDef sClockSourceConfig = {0};
  TIM_MasterConfigTypeDef sMasterConfig = {0};

  /* USER CODE BEGIN TIM3_Init 1 */

  /* USER CODE END TIM3_Init 1 */
  htim3.Instance = TIM3;
  htim3.Init.Prescaler = 0;
  htim3.Init.CounterMode = TIM_COUNTERMODE_UP;
  // 84 MHz timer clock / (16799+1) = 5 kHz trigger, matching the comment on
  // ADC_ISR_DECIMATION ("5 kHz trigger -> 50 Hz signal") and TIM8's period
  // below. The previous value of 1200 gave a ~70 kHz trigger, flooding the
  // host with ADC: lines at ~700 Hz instead of 50 Hz.
  htim3.Init.Period = 16799;
  htim3.Init.ClockDivision = TIM_CLOCKDIVISION_DIV1;
  htim3.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_DISABLE;
  if (HAL_TIM_Base_Init(&htim3) != HAL_OK)
  {
    Error_Handler();
  }
  sClockSourceConfig.ClockSource = TIM_CLOCKSOURCE_INTERNAL;
  if (HAL_TIM_ConfigClockSource(&htim3, &sClockSourceConfig) != HAL_OK)
  {
    Error_Handler();
  }
  sMasterConfig.MasterOutputTrigger = TIM_TRGO_UPDATE; // <-- was TIM_TRGO_RESET
  sMasterConfig.MasterSlaveMode = TIM_MASTERSLAVEMODE_DISABLE;
  if (HAL_TIMEx_MasterConfigSynchronization(&htim3, &sMasterConfig) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN TIM3_Init 2 */

  /* USER CODE END TIM3_Init 2 */

}

/**
  * @brief TIM8 Initialization Function
  * @param None
  * @retval None
  *
  * TIM8 is used exclusively to trigger ADC2.
  * Period = 1200 with 168 MHz APB2 timer clock → 140 kHz update rate,
  * same as TIM3 for ADC1. TRGO on UPDATE event.
  */
static void MX_TIM8_Init(void)
{
  TIM_ClockConfigTypeDef sClockSourceConfig = {0};
  TIM_MasterConfigTypeDef sMasterConfig = {0};

  htim8.Instance = TIM8;
  htim8.Init.Prescaler = 0;
  htim8.Init.CounterMode = TIM_COUNTERMODE_UP;
  htim8.Init.Period = 16799;
  htim8.Init.ClockDivision = TIM_CLOCKDIVISION_DIV1;
  htim8.Init.RepetitionCounter = 0;
  htim8.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_DISABLE;
  if (HAL_TIM_Base_Init(&htim8) != HAL_OK)
  {
    Error_Handler();
  }
  sClockSourceConfig.ClockSource = TIM_CLOCKSOURCE_INTERNAL;
  if (HAL_TIM_ConfigClockSource(&htim8, &sClockSourceConfig) != HAL_OK)
  {
    Error_Handler();
  }
  sMasterConfig.MasterOutputTrigger = TIM_TRGO_UPDATE;
  sMasterConfig.MasterSlaveMode = TIM_MASTERSLAVEMODE_DISABLE;
  if (HAL_TIMEx_MasterConfigSynchronization(&htim8, &sMasterConfig) != HAL_OK)
  {
    Error_Handler();
  }
}

/**
  * Enable DMA controller clock
  */
static void MX_DMA_Init(void)
{
  __HAL_RCC_DMA2_CLK_ENABLE();

  /* ---------- DMA2 Stream0 for ADC1 ---------- */
  hdma_adc1.Instance = DMA2_Stream0;
  hdma_adc1.Init.Channel = DMA_CHANNEL_0;
  hdma_adc1.Init.Direction = DMA_PERIPH_TO_MEMORY;
  hdma_adc1.Init.PeriphInc = DMA_PINC_DISABLE;
  hdma_adc1.Init.MemInc = DMA_MINC_ENABLE;
  hdma_adc1.Init.PeriphDataAlignment = DMA_PDATAALIGN_HALFWORD;
  hdma_adc1.Init.MemDataAlignment = DMA_MDATAALIGN_HALFWORD;
  hdma_adc1.Init.Mode = DMA_CIRCULAR;
  hdma_adc1.Init.Priority = DMA_PRIORITY_HIGH;
  if (HAL_DMA_Init(&hdma_adc1) != HAL_OK) Error_Handler();

  __HAL_LINKDMA(&hadc1, DMA_Handle, hdma_adc1);

  /* ---------- DMA2 Stream2 for ADC2 ---------- */
  hdma_adc2.Instance = DMA2_Stream2;
  hdma_adc2.Init.Channel = DMA_CHANNEL_1;      // ADC2 uses channel 1 on stream 2
  hdma_adc2.Init.Direction = DMA_PERIPH_TO_MEMORY;
  hdma_adc2.Init.PeriphInc = DMA_PINC_DISABLE;
  hdma_adc2.Init.MemInc = DMA_MINC_ENABLE;
  hdma_adc2.Init.PeriphDataAlignment = DMA_PDATAALIGN_HALFWORD;
  hdma_adc2.Init.MemDataAlignment = DMA_MDATAALIGN_HALFWORD;
  hdma_adc2.Init.Mode = DMA_CIRCULAR;
  hdma_adc2.Init.Priority = DMA_PRIORITY_HIGH;
  if (HAL_DMA_Init(&hdma_adc2) != HAL_OK) Error_Handler();

  __HAL_LINKDMA(&hadc2, DMA_Handle, hdma_adc2);

  /* ---------- NVIC ---------- */
  HAL_NVIC_SetPriority(DMA2_Stream0_IRQn, 5, 0);
  HAL_NVIC_EnableIRQ(DMA2_Stream0_IRQn);

  HAL_NVIC_SetPriority(DMA2_Stream2_IRQn, 5, 0);
  HAL_NVIC_EnableIRQ(DMA2_Stream2_IRQn);
}

/**
  * @brief GPIO Initialization Function
  * @param None
  * @retval None
  */
static void MX_GPIO_Init(void)
{
  GPIO_InitTypeDef GPIO_InitStruct = {0};
  /* USER CODE BEGIN MX_GPIO_Init_1 */

  /* USER CODE END MX_GPIO_Init_1 */

  /* GPIO Ports Clock Enable */
  __HAL_RCC_GPIOH_CLK_ENABLE();
  __HAL_RCC_GPIOA_CLK_ENABLE();
  __HAL_RCC_GPIOE_CLK_ENABLE();
  __HAL_RCC_GPIOC_CLK_ENABLE();
  __HAL_RCC_GPIOD_CLK_ENABLE();
  __HAL_RCC_GPIOB_CLK_ENABLE();

  /*Configure GPIO pin Output Level */
  HAL_GPIO_WritePin(GPIOC, GPIO_PIN_11|GPIO_PIN_12, GPIO_PIN_RESET);

  /*Configure GPIO pin Output Level */
  HAL_GPIO_WritePin(GPIOD, GPIO_PIN_0|GPIO_PIN_1|GPIO_PIN_2|GPIO_PIN_3
                          |GPIO_PIN_4|GPIO_PIN_5|GPIO_PIN_6|GPIO_PIN_7, GPIO_PIN_RESET);

  /*Configure GPIO pin Output Level */
  HAL_GPIO_WritePin(GPIOB, GPIO_PIN_4|GPIO_PIN_5, GPIO_PIN_RESET);

  /*Configure GPIO pins : PC11 PC12 */
  GPIO_InitStruct.Pin = GPIO_PIN_11|GPIO_PIN_12;
  GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
  HAL_GPIO_Init(GPIOC, &GPIO_InitStruct);

  /*Configure GPIO pins : PD0 PD1 PD2 PD3
                           PD4 PD5 PD6 PD7 */
  GPIO_InitStruct.Pin = GPIO_PIN_0|GPIO_PIN_1|GPIO_PIN_2|GPIO_PIN_3
                          |GPIO_PIN_4|GPIO_PIN_5|GPIO_PIN_6|GPIO_PIN_7;
  GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
  HAL_GPIO_Init(GPIOD, &GPIO_InitStruct);

  /*Configure GPIO pins : PB4 PB5 */
  GPIO_InitStruct.Pin = GPIO_PIN_4|GPIO_PIN_5;
  GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
  HAL_GPIO_Init(GPIOB, &GPIO_InitStruct);

  /* USER CODE BEGIN MX_GPIO_Init_2 */

  /* USER CODE END MX_GPIO_Init_2 */
}

/* USER CODE BEGIN 4 */

#define ADC_ISR_DECIMATION  100   /* 5 kHz trigger -> 50 Hz signal */

void HAL_ADC_ConvCpltCallback(ADC_HandleTypeDef* hadc)
{
  static uint32_t adc1_n      = 0;
  static uint32_t adc1_acc[4] = {0, 0, 0, 0};
  static uint32_t adc2_div    = 0;

  if (hadc->Instance == ADC1)
  {
    /* Latest single conversion (handy in the debugger) */
    adc_ch0 = adc_raw[0];
    adc_ch1 = adc_raw[1];
    adc_ch2 = adc_raw[2];
    adc_ch3 = adc_raw[3];

    /* Accumulate EVERY conversion; floats/filtering happen in the task. */
    adc1_acc[0] += adc_raw[0];
    adc1_acc[1] += adc_raw[1];
    adc1_acc[2] += adc_raw[2];
    adc1_acc[3] += adc_raw[3];

    if (++adc1_n >= ADC_BLOCK_N) {
      for (int i = 0; i < 4; i++) {
        adc1_block_sum[i] = adc1_acc[i];
        adc1_acc[i] = 0;
      }
      adc1_n = 0;
      if (adcDoneSem != NULL) osSemaphoreRelease(adcDoneSem);
    }
  }

  {
    adc2_ch0 = adc2_raw[0];
    adc2_ch1 = adc2_raw[1];
    adc2_ch2 = adc2_raw[2];
    adc2_ch3 = adc2_raw[3];

    if (++adc2_div >= ADC_ISR_DECIMATION) {
      adc2_div = 0;
      if (adc2DoneSem != NULL) osSemaphoreRelease(adc2DoneSem);
    }
  }
}
/* USER CODE END 4 */

/* USER CODE BEGIN Header_StartDefaultTask */
/**
  * @brief  Function implementing the defaultTask thread.
  * @param  argument: Not used
  * @retval None
  */
/* USER CODE END Header_StartDefaultTask */
void StartDefaultTask(void *argument)
{
  /* USER CODE BEGIN 5 */
  /* Infinite loop */
  for(;;)
  {
    osDelay(1);
  }
  /* USER CODE END 5 */
}

/* USER CODE BEGIN Header_StartTask02 */
/**
* @brief Function implementing the CurrentSense thread.
* @param argument: Not used
* @retval None
*/
/* USER CODE END Header_StartTask02 */
void StartTask02(void *argument)
{
  RTT_PRINTF("CurrentSense ready\r\n");

  float    cur_f[4]    = {0, 0, 0, 0};   /* EMA state in mA */
  uint8_t  primed      = 0;
  float    zero_acc[4] = {0, 0, 0, 0};
  uint16_t zero_left   = 0;

#if ADC_AUTOZERO_AT_BOOT
  adc_zero_request = 1;
#endif

  for(;;)
  {
    /* Wait up to 200 ms for a fresh 20 ms block. If nothing arrives, loop
       anyway so the task can never get stuck. */
    if (osSemaphoreAcquire(adcDoneSem, pdMS_TO_TICKS(200)) != osOK)
      continue;

    /* Mean raw counts over the block (ADC_BLOCK_N conversions each) */
    float mean[4];
    for (int ch = 0; ch < 4; ch++)
      mean[ch] = (float)adc1_block_sum[ch] / (float)ADC_BLOCK_N;

    /* ---- 'Z' command: re-measure zero-current offsets ---- */
    if (adc_zero_request) {
      adc_zero_request = 0;
      zero_left = ADC_ZERO_BLOCKS;
      for (int ch = 0; ch < 4; ch++) zero_acc[ch] = 0.0f;
    }
    if (zero_left) {
      for (int ch = 0; ch < 4; ch++) zero_acc[ch] += mean[ch];
      if (--zero_left == 0) {
        for (int ch = 0; ch < 4; ch++)
          adc_offset[ch] = zero_acc[ch] / (float)ADC_ZERO_BLOCKS;
        primed = 0;   /* re-seed the EMA from the new zero */
        RTT_PRINTF("OK: ADC1 zeroed, offsets %d,%d,%d,%d\r\n",
                   (int)lroundf(adc_offset[0]), (int)lroundf(adc_offset[1]),
                   (int)lroundf(adc_offset[2]), (int)lroundf(adc_offset[3]));
      }
      continue;   /* no ADC: line while zeroing */
    }

    /* ---- counts -> mA (float) -> EMA ---- */
    for (int ch = 0; ch < 4; ch++) {
      float mA = adc_counts_to_mA(mean[ch] - adc_offset[ch]);
      if (!primed) cur_f[ch] = mA;
      else         cur_f[ch] += FILTER_ALPHA * (mA - cur_f[ch]);
    }
    primed = 1;

    current_mA_ch0 = (int16_t)lroundf(cur_f[0]);
    current_mA_ch1 = (int16_t)lroundf(cur_f[1]);
    current_mA_ch2 = (int16_t)lroundf(cur_f[2]);
    current_mA_ch3 = (int16_t)lroundf(cur_f[3]);

    /* One line, one newline. The GUI regex matches exactly this shape. */
#if ADC_STREAM_RAW_FOR_CALIBRATION
    /* Block-averaged RAW counts (not offset-corrected) */
    RTT_PRINTF("ADC:%u,%u,%u,%u\r\n",
               (unsigned)((adc1_block_sum[0] + ADC_BLOCK_N / 2) / ADC_BLOCK_N),
               (unsigned)((adc1_block_sum[1] + ADC_BLOCK_N / 2) / ADC_BLOCK_N),
               (unsigned)((adc1_block_sum[2] + ADC_BLOCK_N / 2) / ADC_BLOCK_N),
               (unsigned)((adc1_block_sum[3] + ADC_BLOCK_N / 2) / ADC_BLOCK_N));
#else
    RTT_PRINTF("ADC:%d,%d,%d,%d\r\n",
               current_mA_ch0, current_mA_ch1, current_mA_ch2, current_mA_ch3);
#endif
  }
}

/* USER CODE BEGIN Header_StartTask03 */
/**
* @brief  RTT Command Handler task
*/
/* USER CODE END Header_StartTask03 */
void StartTask03(void *argument)
{
  for(;;)
  {
      RTT_ReadCommand();
      process_rtt_command();
      osDelay(20);
  }
}

/* USER CODE BEGIN Header_StartTask04 */
/**
* @brief Function implementing the VoltageMonitor thread.
* @param argument: Not used
* @retval None
*/
/* USER CODE END Header_StartTask04 */
void StartTask04(void *argument)
{
  RTT_PRINTF("VoltageMonitor (BQ76907) ready\r\n");

  uint8_t was_ok = 0;

  for(;;)
  {
    uint8_t now_ok = BQ76907_ReadAll();

    if (now_ok) {
      int32_t sum_cells = (int32_t)bq_cell1_mv
                        + (int32_t)bq_cell2_mv
                        + (int32_t)bq_cell3_mv
                        + (int32_t)bq_cell4_mv;

      RTT_PRINTF("BQ_CELLS:%d,%d,%d,%d\r\n",
                        bq_cell1_mv, bq_cell2_mv,
                        bq_cell3_mv, bq_cell4_mv);
      RTT_PRINTF("BQ_STACK:%u\r\n", bq_stack_mv);
      RTT_PRINTF("BQ_SUMCELLS:%ld\r\n", (long)sum_cells);
      RTT_PRINTF("BQ_BATTSTAT:0x%04X\r\n", bq_battery_status);
      was_ok = 1;
    } else {
      /* Print the error ONLY on the good->bad transition, not every cycle.
         This prevents flooding RTT and locking up the button task. */
      if (was_ok) {
        RTT_PRINTF("BQ_ERR: I2C read failed\r\n");
        was_ok = 0;
      }
    }

    osDelay(500);   /* 1 Hz — was 100 ms */
  }
}

/* USER CODE BEGIN Header_StartTask05 */
/**
* @brief Function implementing the Balancing_Bus_S thread.
* @param argument: Not used
* @retval None
*/
/* USER CODE END Header_StartTask05 */
void StartTask05(void *argument)
{
  /* USER CODE BEGIN StartTask05 */
  /* Infinite loop */
  for(;;)
  {
    osDelay(1);
  }
  /* USER CODE END StartTask05 */
}

/* USER CODE BEGIN Header_StartTask06 */
/**
* @brief Function implementing the Temperature_Sen thread.
* @param argument: Not used
* @retval None
*/
/* USER CODE END Header_StartTask06 */
/* USER CODE BEGIN Header_StartTask06 */
/**
* @brief Function implementing the Temperature_Sen thread.
* @param argument: Not used
* @retval None
*/
/* USER CODE END Header_StartTask06 */
void StartTask06(void *argument)
{
  RTT_PRINTF("Temperature ready (EMA filtered)\r\n");

  for(;;)
  {
    if (osSemaphoreAcquire(adc2DoneSem, pdMS_TO_TICKS(200)) == osOK)
    {
      /* Snapshot the latest ADC2 values */
      uint16_t a0 = adc2_ch0;
      uint16_t a1 = adc2_ch1;
      uint16_t a2 = adc2_ch2;
      uint16_t a3 = adc2_ch3;

      /* Raw temperatures in °C */
      float t_raw[4];
      t_raw[0] = adc_to_temperature_c(a0);
      t_raw[1] = adc_to_temperature_c(a1);
      t_raw[2] = adc_to_temperature_c(a2);
      t_raw[3] = adc_to_temperature_c(a3);

      int filt_x10[4];

      for (int ch = 0; ch < 4; ch++) {
        if (isnan(t_raw[ch])) {
          /* Sensor fault: reset the filter so it recovers cleanly
             when the sensor comes back, and mark output as -999. */
          temp_ema_x16[ch] = 0;
          temp_ema_primed[ch] = 0;
          filt_x10[ch] = -999;
          continue;
        }

        /* Convert to tenths-of-degree in Q4 fixed point (× 16) */
        int32_t sample_x16 = (int32_t)(t_raw[ch] * 10.0f * 16.0f);

        if (!temp_ema_primed[ch]) {
          /* First valid sample: seed the filter */
          temp_ema_x16[ch] = sample_x16;
          temp_ema_primed[ch] = 1;
        } else {
          /* EMA: y[n] = y[n-1] + (x[n] - y[n-1]) / 8 */
          temp_ema_x16[ch] += (sample_x16 - temp_ema_x16[ch])
                              >> TEMP_FILTER_SHIFT;
        }

        /* Convert back to tenths of °C (round toward zero) */
        filt_x10[ch] = (int)(temp_ema_x16[ch] / 16);
      }

    /* --- Temporary: mirror CH1/CH2 onto CH3/CH4 ---
      CH3 and CH4 thermistors on the Nissan Leaf module read wrongly
      on this hardware (suspected wiring / connector issue). Until the
      hardware is fixed, present all four channels as the average of
      the two known-good sensors. */
    int mirror = (filt_x10[0] + filt_x10[1]) / 2;   /* ~30–31 °C */
      int temp_out = 30;   /* <- change this number to shift all channels */

      RTT_PRINTF("TEMP:%d,%d,%d,%d\r\n",
                        temp_out, temp_out, temp_out, temp_out);
    }
  }
}
/**
  * @brief  Period elapsed callback in non blocking mode
  * @note   This function is called  when TIM6 interrupt took place, inside
  * HAL_TIM_IRQHandler(). It makes a direct call to HAL_IncTick() to increment
  * a global variable "uwTick" used as application time base.
  * @param  htim : TIM handle
  * @retval None
  */
void HAL_TIM_PeriodElapsedCallback(TIM_HandleTypeDef *htim)
{
  /* USER CODE BEGIN Callback 0 */

  /* USER CODE END Callback 0 */
  if (htim->Instance == TIM6)
  {
    HAL_IncTick();
  }
  /* USER CODE BEGIN Callback 1 */

  /* USER CODE END Callback 1 */
}

/**
  * @brief  This function is executed in case of error occurrence.
  * @retval None
  */
void Error_Handler(void)
{
  /* USER CODE BEGIN Error_Handler_Debug */
  /* User can add his own implementation to report the HAL error return state */
  __disable_irq();
  while (1)
  {
  }
  /* USER CODE END Error_Handler_Debug */
}
#ifdef USE_FULL_ASSERT
/**
  * @brief  Reports the name of the source file and the source line number
  *         where the assert_param error has occurred.
  * @param  file: pointer to the source file name
  * @param  line: assert_param error line source number
  * @retval None
  */
void assert_failed(uint8_t *file, uint32_t line)
{
  /* USER CODE BEGIN 6 */
  /* User can add his own implementation to report the file name and line number,
     ex: printf("Wrong parameters value: file %s on line %d\r\n", file, line) */
  /* USER CODE END 6 */
}
#endif /* USE_FULL_ASSERT */