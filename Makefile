PYTHON_SETUP	=	python setup.py

isort:
	find . -name '*.py' | xargs isort --profile django

spell:
	-find . -name '*.py' | xargs codespell -w

black: isort
	find . -name '*.py' | xargs black -l 119 -t py313

djhtml:
	djhtml apps/ templates/

check:
	python manage.py check

commit:	_commit

_commit: spell isort black djhtml check
	git add apps/
	git commit -a
	git push origin

restart:
	sudo systemctl restart gunicorn
	sudo systemctl restart celery
	sudo systemctl restart celery_beat

FORCE:
