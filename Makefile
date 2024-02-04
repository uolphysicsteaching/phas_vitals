PYTHON_SETUP	=	python setup.py

isort:
	find . -name '*.py' -exec isort --profile black {} \;

spell:
	-find . -name '*.py' | xargs codespell -w

black: isort
	find . -name '*.py' -exec black -l 119 {} \;


check:
	python manage.py check

commit:	_commit

_commit: spell isort black check
	git add apps/
	git commit -a
	git push origin master

permissions:
	setfacl --set-file=/home/phygbu/acls.txt -R apps/
	setfacl --set-file=/home/phygbu/acls.txt -R phy_srv4125/

restart: permissions
	django-restart .

FORCE:
