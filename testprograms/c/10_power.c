#include <stdio.h>

int main() {
    int base, exp, i;
    int result = 1;
    scanf("%d", &base);
    scanf("%d", &exp);
    for (i = 0; i < exp; i++) {
        result = result * base;
    }
    printf("Result: %d\n", result);
    return 0;
}
