for x in range(3):
    print(x)

iterator = iter(range(3))
print(type(iterator))
while True:
    try:
        x = next(iterator)
        print(x)
    except StopIteration as ex:
        print(ex)
        break


def my_range(n):
    i = 0
    while i < n:
        yield i
        i += 1


generator: iter = my_range(3)
print(type(generator))
