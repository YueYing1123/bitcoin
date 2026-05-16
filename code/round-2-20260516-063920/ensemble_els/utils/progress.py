# -*- coding: utf-8 -*-
from contextlib import contextmanager
from typing import Iterable
from tqdm import tqdm


def iter_with_progress(iterable: Iterable, desc: str = "", total: int | None = None):
	return tqdm(iterable, desc=desc, total=total, ncols=100)


@contextmanager
def progress_bar(total: int, desc: str = ""):
	bar = tqdm(total=total, desc=desc, ncols=100)
	try:
		yield bar
	finally:
		bar.close()


