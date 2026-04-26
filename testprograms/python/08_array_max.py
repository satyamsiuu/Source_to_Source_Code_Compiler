n = int(input())
arr = [0] * n
for i in range(n):
    arr[i] = int(input())
maximum = arr[0]
for i in range(1, n):
    if arr[i] > maximum:
        maximum = arr[i]
print("Maximum:", maximum)
