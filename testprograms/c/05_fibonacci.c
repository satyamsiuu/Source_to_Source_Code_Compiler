#include <stdio.h>

int main() {
    int n, i;
    scanf("%d", &n);
    int a = 0;
    int b = 1;
    printf("%d\n", a);
    printf("%d\n", b);
    for (i = 2; i < n; i++) {
        int c = a + b;
        printf("%d\n", c);
        a = b;
        b = c;
    }
    return 0;
}
