import time
import numpy as np

size = 10_000  # adjust if needed

start = time.time()

a = np.random.rand(size, size)
b = np.random.rand(size, size)

c = a @ b  # matrix multiplication

end = time.time()

print(f"Matrix mult took {end - start:.2f} seconds")