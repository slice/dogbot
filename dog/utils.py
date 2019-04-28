def chained_decorators(decorators):
    def decorator(func):
        for decorator in decorators:
            func = decorator(func)
        return func
    return decorator
