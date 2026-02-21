# Backgrounds

I like [jnthas/clockwise: do-it-yourself, full-featured and smart wall clock device](https://github.com/jnthas/clockwise), but I only have a Pi Pico 2W, and a 64x64 LED. [gallaugher/pico-and-hub75-led-matrix: Wiring & code to run a "Happy Graduation" on a Raspberry Pi Pico with a 64 x 32 HUB75 LED Matrix DIsplay](https://github.com/gallaugher/pico-and-hub75-led-matrix) is the closed thing I can find. So I forked it and try to make a small clock out of it.

# Hardware changes

Most of the documents in the parent repo still works, except these two:

- Because I want WiFi/NTP support, it needs to be a board with wifi. I'm using Pi Pico 2W
- Because I'm using a 64x64 LED matrix, so I connected the "empty" ping on HUB75 to GP21 on the Pico
<img width="800" height="450" alt="improved wiring diagram for hub75 and pico" src="https://github.com/user-attachments/assets/0985a79c-e9b0-41b5-bbf1-3da0da7d6aa4" />



