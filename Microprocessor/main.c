#include <xc.h>

// Configuration word
#pragma config FOSC = HS        // High-speed oscillator
#pragma config WDTE = OFF       // Watchdog Timer disabled
#pragma config PWRTE = ON       // Power-up Timer enabled
#pragma config MCLRE = ON       // MCLR pin enabled
#pragma config BOREN = ON       // Brown-out Reset enabled
#pragma config LVP = OFF        // Low-voltage programming disabled
#pragma config CPD = OFF        // Data memory code protection off
#pragma config CP = OFF         // Program memory code protection off

// Define pins
#define LED1 RB4
#define LED2 RB5

// Function prototypes
void InitComparator(void);

// Main function
void main(void) {
    TRISB4 = 0;  // Configure RB4 as output
    TRISB5 = 0;  // Configure RB5 as output
    LED1 = 0;    // Turn off LED1
    LED2 = 0;    // Turn off LED2

    InitComparator();  // Initialize comparator

    while (1) {
        if (C1OUT) {        // If comparator 1 output is high
            LED1 = 1;       // Turn on LED1
        } else {
            LED1 = 0;       // Turn off LED1
        }

        if (C2OUT) {        // If comparator 2 output is high
            LED2 = 1;       // Turn on LED2
        } else {
            LED2 = 0;       // Turn off LED2
        }
    }
}

// Function to initialize the comparator
void InitComparator(void) {
    TRISA0 = 1;      // Set RA0 as input (C1IN0-)
    TRISA1 = 1;      // Set RA1 as input (C1IN+)
    TRISA2 = 1;      // Set RA2 as input (C2IN0-)
    TRISA3 = 1;      // Set RA3 as input (C2IN+)

    // Note: PIC16F628A does not have ANSEL register.
    // Setting CMCON = 0x02 configures RA0-RA3 as analog inputs for the comparators.
    CMCON = 0x02;    // Enable comparators: RA0/RA1 for C1, RA2/RA3 for C2
    VRCON = 0x88;    // Enable internal voltage reference (2.5V)
}
