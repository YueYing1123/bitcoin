# -*- coding: utf-8 -*-
import time
import logging
from typing import Callable, Type, Tuple


def retry(
	max_retries: int = 12,
	backoff_base: float = 1.5,
	retry_on: Tuple[Type[BaseException], ...] = (Exception,),
	logger: logging.Logger = logging.getLogger(__name__),
) -> Callable:
	def decorator(func: Callable) -> Callable:
		def wrapper(*args, **kwargs):
			attempt = 0
			while True:
				try:
					return func(*args, **kwargs)
				except retry_on as e:
					attempt += 1
					logger.error(f"Error on attempt {attempt}: {e}")
					if attempt >= max_retries:
						raise
					sleep_s = (backoff_base ** (attempt - 1))
					time.sleep(min(sleep_s, 30))
		return wrapper
	return decorator


