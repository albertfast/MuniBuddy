import torch

def test_gpu():
    print("CUDA available:", torch.cuda.is_available())
    print("Current device:", torch.cuda.current_device())
    print("Device name:", torch.cuda.get_device_name(0))
    a = torch.rand(10000, device='cuda')
    b = torch.rand(10000, device='cuda')
    c = a * b
    print("Computation result (sum):", c.sum().item())
