#include <iostream>
using namespace std;

int main() {
    int n, i;
    cin >> n;
    int a = 0;
    int b = 1;
    cout << a << endl;
    cout << b << endl;
    for (i = 2; i < n; i++) {
        int c = a + b;
        cout << c << endl;
        a = b;
        b = c;
    }
    return 0;
}
