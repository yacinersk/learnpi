import requests

def verify_pi_token(access_token):
    if not access_token:
        return None
    try:
        res = requests.get(
            "https://api.minepi.com/v2/me",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=5
        )
        if res.status_code == 200:
            data = res.json()
            if "uid" in data and "username" in data:
                return data
    except requests.exceptions.RequestException as e:
        print(f"[verify_pi_token] Network error: {e}")
    return None
