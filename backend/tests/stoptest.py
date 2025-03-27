stop = {'stop_id': '14212'}  # Example stop dictionary
original_stop_id = stop['stop_id']
api_stop_id = original_stop_id[1:] if original_stop_id.startswith('1') else original_stop_id
print(f"Original: {original_stop_id}, API: {api_stop_id}")  # For testing