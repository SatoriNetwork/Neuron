

def check_headless_yaml():
    try:
        import yaml
        with open('../../config/config.yaml', 'r') as f:
            config = yaml.safe_load(f)
        return config.get('headless', False)
    except Exception as _:
        return False


if __name__ == "__main__":
    headless = check_headless_yaml()
    print(headless)
