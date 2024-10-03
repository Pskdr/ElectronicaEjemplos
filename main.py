import machine
import time
from _thread import start_new_thread

# Pines de los LEDs
PIN_LED_LLENADO = 12
PIN_LED_VACIADO = 27
PIN_LED_EMERGENCIA = 25

# Pines de los botones
PIN_BOTON_LLENADO = 15
PIN_BOTON_VACIADO = 4
PIN_BOTON_PARO = 5

# Pines de los sensores
PIN_ULTRASONICO_TRIGGER = 23
PIN_ULTRASONICO_ECHO = 22
PIN_TEMPERATURA = 26

# Configuración de niveles
MIN_NIVEL_CM = 5    # Tanque lleno (5 cm)
MAX_NIVEL_CM = 50   # Tanque vacío (50 cm)

# Umbral de temperatura
UMBRAL_TEMPERATURA = 30  # Grados Celsius

class SensorTemperatura:
    def __init__(self, pin):
        self.sensor = machine.ADC(machine.Pin(pin))
        self.sensor.atten(machine.ADC.ATTN_11DB)

    def compute_temp(self, avg_a):
        lm35_v = avg_a * (3.3 / 65535)  # Lectura analógica a voltaje
        tmp_c = round((lm35_v * 100), 2)  # Grados Celsius
        return tmp_c

    def leer_temperatura(self, total_samples=20):
        samples = 0
        for _ in range(total_samples):
            samples += self.sensor.read_u16()
            time.sleep(0.1)

        avg_a = samples / total_samples
        return self.compute_temp(avg_a)

class SensorUltrasonico:
    def __init__(self, trig_pin, echo_pin):
        self.trig = machine.Pin(trig_pin, machine.Pin.OUT)
        self.echo = machine.Pin(echo_pin, machine.Pin.IN)

    def medir_distancia(self):
        self.trig.value(0)
        time.sleep_us(2)

        self.trig.value(1)
        time.sleep_us(10)
        self.trig.value(0)

        max_wait = 10000
        start_wait = time.ticks_us()
        while self.echo.value() == 0:
            if time.ticks_diff(time.ticks_us(), start_wait) > max_wait:
                print("Timeout esperando el pulso de eco")
                return None

        start_time = time.ticks_us()
        while self.echo.value() == 1:
            if time.ticks_diff(time.ticks_us(), start_time) > max_wait:
                print("Timeout midiendo la duración del pulso de eco")
                return None

        end_time = time.ticks_us()
        duration = time.ticks_diff(end_time, start_time)
        distance_cm = (duration * 0.0343) / 2

        if distance_cm <= 0 or distance_cm > 250:
            print("Medición fuera de rango")
            return None

        return distance_cm

class ControlTanque:
    def __init__(self):
        self.llenado_activo = False
        self.vaciado_activo = False
        self.sensor_temp = SensorTemperatura(PIN_TEMPERATURA)
        self.sensor_ultrasonico = SensorUltrasonico(PIN_ULTRASONICO_TRIGGER, PIN_ULTRASONICO_ECHO)

    def iniciar_llenado(self):
        if not self.llenado_activo:
            self.vaciado_activo = False  # Detener vaciado si estaba activo
            self.llenado_activo = True
            machine.Pin(PIN_LED_LLENADO, machine.Pin.OUT).on()  # Encender LED de llenado
            print("Iniciando llenado...")

            while self.llenado_activo:
                # Verificar el estado del botón de paro de emergencia
                if machine.Pin(PIN_BOTON_PARO).value() == 0:  # Verificar si el botón está presionado
                    self.paro_emergencia()
                    return  # Salir del método inmediatamente
                
                distancia = self.sensor_ultrasonico.medir_distancia()
                temperatura = self.sensor_temp.leer_temperatura()  # Leer temperatura
                
                # Verificar si la temperatura excede el umbral
                if temperatura > UMBRAL_TEMPERATURA:
                    print("Temperatura excede el umbral, activando paro de emergencia.")
                    self.paro_emergencia()
                    return  # Salir del método
                
                if distancia is not None:
                    # Calcular el nivel del tanque como distancia + 5 cm
                    nivel_tanque = distancia + MIN_NIVEL_CM  # Invirtiendo el cálculo
                    print(f"Llenando tanque: {nivel_tanque} cm de {MAX_NIVEL_CM} cm")
                    
                    # Verificar si el tanque está lleno
                    if distancia <= MIN_NIVEL_CM:
                        print("El tanque está lleno.")
                        self.llenado_activo = False
                        machine.Pin(PIN_LED_LLENADO, machine.Pin.OUT).off()  # Apagar LED de llenado
                        return  # Salir del método
                time.sleep(0.5)  # Esperar 0.5 segundos entre lecturas

    def iniciar_vaciado(self):
        if not self.vaciado_activo:
            self.llenado_activo = False  # Detener llenado si estaba activo
            print("Iniciando vaciado...")
            machine.Pin(PIN_LED_LLENADO, machine.Pin.OUT).off()  # Apagar LED de llenado
            self.vaciado_activo = True
            machine.Pin(PIN_LED_VACIADO, machine.Pin.OUT).on()  # Encender LED de vaciado

            while self.vaciado_activo:
                # Verificar el estado del botón de paro de emergencia
                if machine.Pin(PIN_BOTON_PARO).value() == 0:  # Verificar si el botón está presionado
                    self.paro_emergencia()
                    return  # Salir del método inmediatamente
                
                temperatura = self.sensor_temp.leer_temperatura()  # Leer temperatura
                
                # Verificar si la temperatura excede el umbral
                if temperatura > UMBRAL_TEMPERATURA:
                    print("Temperatura excede el umbral, activando paro de emergencia.")
                    self.paro_emergencia()
                    return  # Salir del método

                distancia = self.sensor_ultrasonico.medir_distancia()
                if distancia is not None:
                    nivel_tanque = distancia + MIN_NIVEL_CM
                    if nivel_tanque == 0:
                        print("El tanque está vacío.")
                        self.llenado_activo = False
                        machine.Pin(PIN_BOTON_VACIADO, machine.Pin.OUT).off()  # Apagar LED de llenado
                        return  # Salir del método
                    # Calcular el nivel del tanque como distancia + 5 cm
                    print(f"Vaciando tanque: {nivel_tanque} cm de {MAX_NIVEL_CM} cm")
                           
                time.sleep(0.5)  # Esperar 0.5 segundos entre lecturas

    def paro_emergencia(self):
        print("Paro de emergencia activado.")
        self.llenado_activo = False
        self.vaciado_activo = False
        machine.Pin(PIN_LED_LLENADO, machine.Pin.OUT).off()  # Apagar LED de llenado
        machine.Pin(PIN_LED_VACIADO, machine.Pin.OUT).off()  # Apagar LED de vaciado
        start_new_thread(self.titilar_led_emergencia, ())

    def titilar_led_emergencia(self):
        for _ in range(6):  # Titilar 6 veces (3 segundos)
            machine.Pin(PIN_LED_EMERGENCIA, machine.Pin.OUT).on()  # Encender LED de emergencia
            time.sleep(0.5)  # Encendido por 0.5 segundos
            machine.Pin(PIN_LED_EMERGENCIA, machine.Pin.OUT).off()  # Apagar LED de emergencia
            time.sleep(0.5)  # Apagado por 0.5 segundos

    def mostrar_mediciones(self):
        while True:
            temperatura = self.sensor_temp.leer_temperatura()
            distancia = self.sensor_ultrasonico.medir_distancia()
            if distancia is not None:
                # Calcular el nivel del tanque como distancia + 5 cm
                nivel_tanque = distancia + MIN_NIVEL_CM
                print(f"Temperatura: {temperatura} °C, Distancia: {nivel_tanque} cm")
            time.sleep(2)

# Crear la instancia de ControlTanque
control_tanque = ControlTanque()

# Definición de manejadores de interrupción
def manejador_boton_lllenado(pin):
    print("Botón de llenado presionado.")
    control_tanque.iniciar_llenado()

def manejador_boton_vaciado(pin):
    print("Botón de vaciado presionado.")
    control_tanque.iniciar_vaciado()

def manejador_boton_paro(pin):
    print("Botón de paro presionado.")
    control_tanque.paro_emergencia()

# Configuración de interrupciones para los botones
machine.Pin(PIN_BOTON_LLENADO, machine.Pin.IN, machine.Pin.PULL_UP).irq(trigger=machine.Pin.IRQ_FALLING, handler=manejador_boton_lllenado)
machine.Pin(PIN_BOTON_VACIADO, machine.Pin.IN, machine.Pin.PULL_UP).irq(trigger=machine.Pin.IRQ_FALLING, handler=manejador_boton_vaciado)
machine.Pin(PIN_BOTON_PARO, machine.Pin.IN, machine.Pin.PULL_UP).irq(trigger=machine.Pin.IRQ_FALLING, handler=manejador_boton_paro)

# Inicializar los LEDs apagados
machine.Pin(PIN_LED_LLENADO, machine.Pin.OUT).off()
machine.Pin(PIN_LED_VACIADO, machine.Pin.OUT).off()
machine.Pin(PIN_LED_EMERGENCIA, machine.Pin.OUT).off()

# Iniciar el hilo para mostrar mediciones
start_new_thread(control_tanque.mostrar_mediciones, ())

# Bucle infinito para mantener el programa en ejecución
while True:
    time.sleep(1)  # Solo se mantiene en el bucle

