# import torch

# def main():
#     print("Hello from simbli-image-v1!")
#     print(torch.cuda.is_available())
#     print(torch.cuda.get_device_name(0))


# if __name__ == "__main__":
#     main()


import torch

print("Torch version:", torch.__version__)
print("CUDA available:", torch.cuda.is_available())

if torch.cuda.is_available():
    print("GPU:", torch.cuda.get_device_name(0))