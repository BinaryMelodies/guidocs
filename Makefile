
all:
	mkdir -p out
	python3 src/web.py src/data.xml out
	make -C out
	make -C out allbits

clean:
	rm -rf out

distclean: clean
	rm -f *~ src/*~

.PHONY: all

