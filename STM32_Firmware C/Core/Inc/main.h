/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.h
  * @brief          : Header for main.c file.
  *                   This file contains the common defines of the application.
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

/* Define to prevent recursive inclusion -------------------------------------*/
#ifndef __MAIN_H
#define __MAIN_H

#ifdef __cplusplus
extern "C" {
#endif

/* Includes ------------------------------------------------------------------*/
#include "stm32f4xx_hal.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */

/* USER CODE END Includes */

/* Exported types ------------------------------------------------------------*/
/* USER CODE BEGIN ET */

/* USER CODE END ET */

/* Exported constants --------------------------------------------------------*/
/* USER CODE BEGIN EC */

/* USER CODE END EC */

/* Exported macro ------------------------------------------------------------*/
/* USER CODE BEGIN EM */

/* USER CODE END EM */

void HAL_TIM_MspPostInit(TIM_HandleTypeDef *htim);

/* Exported functions prototypes ---------------------------------------------*/
void Error_Handler(void);

/* USER CODE BEGIN EFP */

/* USER CODE END EFP */

/* Private defines -----------------------------------------------------------*/

/* USER CODE BEGIN Private defines */
/* USER CODE BEGIN Private defines */
/* CELL 1 */
#define MT1_PORT GPIOD
#define MT1_PIN  GPIO_PIN_7
#define MB1B_POS_PORT GPIOC
#define MB1B_POS_PIN  GPIO_PIN_12
#define MB1B_NEG_PORT GPIOB
#define MB1B_NEG_PIN  GPIO_PIN_4

/* CELL 2 */
#define MT2_PORT GPIOD
#define MT2_PIN  GPIO_PIN_6
#define MB2B_POS_PORT GPIOC
#define MB2B_POS_PIN  GPIO_PIN_11
#define MB2B_NEG_PORT GPIOD
#define MB2B_NEG_PIN  GPIO_PIN_1

/* CELL 3 */
#define MT3_PORT GPIOD
#define MT3_PIN  GPIO_PIN_5
#define MB3B_POS_PORT GPIOD
#define MB3B_POS_PIN  GPIO_PIN_3
#define MB3B_NEG_PORT GPIOD
#define MB3B_NEG_PIN  GPIO_PIN_2

/* CELL 4 */
#define MT4_PORT GPIOD
#define MT4_PIN  GPIO_PIN_4
#define MB4B_POS_PORT GPIOB
#define MB4B_POS_PIN  GPIO_PIN_5
#define MB4B_NEG_PORT GPIOD
#define MB4B_NEG_PIN  GPIO_PIN_0

/* ========================================= */
/*             CELL 1 MACROS                 */
/* ========================================= */
#define MT1_ON()       HAL_GPIO_WritePin(MT1_PORT, MT1_PIN, GPIO_PIN_SET)
#define MB1B_POS_ON()  HAL_GPIO_WritePin(MB1B_POS_PORT, MB1B_POS_PIN, GPIO_PIN_SET)
#define MB1B_NEG_ON()  HAL_GPIO_WritePin(MB1B_NEG_PORT, MB1B_NEG_PIN, GPIO_PIN_SET)

#define MT1_OFF()      HAL_GPIO_WritePin(MT1_PORT, MT1_PIN, GPIO_PIN_RESET)
#define MB1B_POS_OFF() HAL_GPIO_WritePin(MB1B_POS_PORT, MB1B_POS_PIN, GPIO_PIN_RESET)
#define MB1B_NEG_OFF() HAL_GPIO_WritePin(MB1B_NEG_PORT, MB1B_NEG_PIN, GPIO_PIN_RESET)

/* ========================================= */
/*             CELL 2 MACROS                 */
/* ========================================= */
#define MT2_ON()       HAL_GPIO_WritePin(MT2_PORT, MT2_PIN, GPIO_PIN_SET)
#define MB2B_POS_ON()  HAL_GPIO_WritePin(MB2B_POS_PORT, MB2B_POS_PIN, GPIO_PIN_SET)
#define MB2B_NEG_ON()  HAL_GPIO_WritePin(MB2B_NEG_PORT, MB2B_NEG_PIN, GPIO_PIN_SET)

#define MT2_OFF()      HAL_GPIO_WritePin(MT2_PORT, MT2_PIN, GPIO_PIN_RESET)
#define MB2B_POS_OFF() HAL_GPIO_WritePin(MB2B_POS_PORT, MB2B_POS_PIN, GPIO_PIN_RESET)
#define MB2B_NEG_OFF() HAL_GPIO_WritePin(MB2B_NEG_PORT, MB2B_NEG_PIN, GPIO_PIN_RESET)

/* ========================================= */
/*             CELL 3 MACROS                 */
/* ========================================= */
#define MT3_ON()       HAL_GPIO_WritePin(MT3_PORT, MT3_PIN, GPIO_PIN_SET)
#define MB3B_POS_ON()  HAL_GPIO_WritePin(MB3B_POS_PORT, MB3B_POS_PIN, GPIO_PIN_SET)
#define MB3B_NEG_ON()  HAL_GPIO_WritePin(MB3B_NEG_PORT, MB3B_NEG_PIN, GPIO_PIN_SET)

#define MT3_OFF()      HAL_GPIO_WritePin(MT3_PORT, MT3_PIN, GPIO_PIN_RESET)
#define MB3B_POS_OFF() HAL_GPIO_WritePin(MB3B_POS_PORT, MB3B_POS_PIN, GPIO_PIN_RESET)
#define MB3B_NEG_OFF() HAL_GPIO_WritePin(MB3B_NEG_PORT, MB3B_NEG_PIN, GPIO_PIN_RESET)

/* ========================================= */
/*             CELL 4 MACROS                 */
/* ========================================= */
#define MT4_ON()       HAL_GPIO_WritePin(MT4_PORT, MT4_PIN, GPIO_PIN_SET)
#define MB4B_POS_ON()  HAL_GPIO_WritePin(MB4B_POS_PORT, MB4B_POS_PIN, GPIO_PIN_SET)
#define MB4B_NEG_ON()  HAL_GPIO_WritePin(MB4B_NEG_PORT, MB4B_NEG_PIN, GPIO_PIN_SET)

#define MT4_OFF()      HAL_GPIO_WritePin(MT4_PORT, MT4_PIN, GPIO_PIN_RESET)
#define MB4B_POS_OFF() HAL_GPIO_WritePin(MB4B_POS_PORT, MB4B_POS_PIN, GPIO_PIN_RESET)
#define MB4B_NEG_OFF() HAL_GPIO_WritePin(MB4B_NEG_PORT, MB4B_NEG_PIN, GPIO_PIN_RESET)
/* USER CODE END Private defines */

#ifdef __cplusplus
}
#endif

#endif /* __MAIN_H */
