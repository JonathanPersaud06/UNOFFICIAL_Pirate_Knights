# Simulated Server Hardware State Layer
storage_remaining_gb = 256.0

def get_storage_string():
    global storage_remaining_gb
    return f"{storage_remaining_gb:.1f} GB"

def subtract_storage(amount_gb):
    global storage_remaining_gb
    storage_remaining_gb = max(0.0, storage_remaining_gb - amount_gb)