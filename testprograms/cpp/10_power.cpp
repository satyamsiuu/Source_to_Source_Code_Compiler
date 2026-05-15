#include <iostream>
using namespace std;

int main() {
    int base, exp, i;
    int result = 1;
    cin >> base;
    cin >> exp;
    for (i = 0; i < exp; i++) {
        result = result * base;
    }
    cout << "Result: " << result;
    return 0;
}
