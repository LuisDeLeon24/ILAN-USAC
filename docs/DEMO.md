# Recorrido de 5 minutos

Haz la carga de demostración antes de sentarte con la audiencia. Con el stack en marcha:

```powershell
docker compose run --rm worker python -m app.demo_frames
docker compose run --rm --no-deps api python -m app.seed --reset
```

Abre http://localhost:3000. Esa pantalla es la presentación pública: no pide sesión y no carga datos de la API. Cada sección ocupa la ventana. Las flechas, Av Pág, Re Pág y la barra espaciadora pasan de una a otra, con desplazamiento suave. La rueda y el dedo también. Los puntos a la derecha marcan la sección y saltan a ella.

Si ya hay sesión, **Ingresar al centro de monitoreo** abre Sitios. Si no, abre el inicio de sesión en `/login`.

Las cámaras están apagadas a propósito. Si las dejas encendidas, el worker analiza el video y suma eventos encima de la semana cargada.

## 0:00 — Qué es

Pantalla: presentación, primera sección. Fondo marino liso, sin el plano de la ciudad. En una pantalla ancha el texto queda a la izquierda y una animación a la derecha; en el teléfono la animación queda debajo del texto. La animación dura unos nueve segundos: una cámara, la detección de una intrusión y la alerta en el panel y en el teléfono. Las demás secciones sí llevan el plano de la ciudad.

Di: "SentinelAI usa las cámaras y los sensores que la planta ya tiene. El video se queda en el sitio. Aquí solo llegan el evento, la foto y los minutos analizados. Se cobra por tiempo analizado, en quetzales."

Recorre las secciones si la audiencia quiere verlas: el problema, la solución, cómo funciona, la privacidad, para quién, el modelo, el impacto, el equipo y el cierre. El cierre repite el mismo botón.

Pulsa **Ingresar al centro de monitoreo**. Entra con el correo y la contraseña de `.env` (`elena.morales@sentinel.com.gt` / `admin12345` si no los cambiaste). El pie de la barra debe decir **Elena Morales** y, debajo, **Administrador**, una sola vez cada uno.

## 0:40 — Dos sitios

Pantalla: Sitios. La lista es lo primero: Planta norte y Bodega central. El formulario no está a la vista. Solo un administrador ve **Agregar sitio**, y el formulario aparece al pulsarlo.

Di: "Una organización, dos sitios. Cada usuario solo ve los datos de su organización."

## 1:10 — Cámaras y una zona

Pantalla: Cámaras. La cuadrícula lista Acceso norte, Patio de carga y Andén bodega. Cada tarjeta dice Inactiva. Abre Acceso norte y pulsa Zonas.

Di: "Son cámaras de archivo para la demo, a 2 cuadros por segundo, apagadas y sin bucle. En un cliente sería RTSP. La zona es un polígono sobre el cuadro: intrusión, fuera de horario, merodeo u ocupación."

Si el cuadro aún no está, di que Actualizar cuadro le pide uno limpio al worker cuando la cámara está encendida, y sigue. No esperes el cuadro si el reloj aprieta.

## 2:00 — Eventos

Pantalla: Eventos. Filtra por severidad alta y luego quita el filtro. Abre una fila con foto. Cambia un evento de nuevo a en revisión.

Di: "La semana trae intrusiones, merodeo, ocupación, fuera de horario, puerta, movimiento y un humo. La foto es un cuadro real del video, con la detección dibujada. El estado lo cambia el operador: nuevo, en revisión, resuelto o falso positivo."

## 2:50 — Métricas

Pantalla: Métricas.

Di: "Esto es el mes en curso, hasta hoy. Acceso norte se analiza todo el día, Patio de carga de 6 a 20, y Andén bodega en el turno de noche. La tarifa es medio centavo de quetzal por minuto, Q 0.005. El tiempo de respuesta es cuánto tardó el primer paso a en revisión. No es una factura: la tarifa se configura aquí."

Si hoy es 1, 2 o 3 del mes, señala la referencia del mes anterior. Di: "El mes acaba de empezar, así que el mes anterior queda al lado para que se vea un mes completo. Los eventos siguen siendo solo esta semana."

## 3:20 — Alertas

Pantalla: Alertas. Muestra el contacto Central de monitoreo, `+50200000000`, inactivo.

Di: "Ese número es un placeholder, y está apagado para que la demo no dispare un WhatsApp. El canal que sí entrega la foto en esta máquina es Telegram. Una cuenta de prueba de Twilio no puede crear plantillas, así que WhatsApp solo manda texto dentro de las 24 horas."

Si el bot ya está vinculado, pulsa Enviar alerta de prueba y enseña el teléfono. Si no, no lo intentes en vivo.

## 3:40 — Puerta y humo

Quédate en el panel. En otra terminal, desde la raíz del repositorio:

```powershell
docker compose exec worker python -m app.simulate_sensor --external-id puerta-norte --state open
docker compose exec worker python -m app.simulate_sensor --external-id humo-planta --state alarm
```

Esos dos sensores están en Planta norte, el sitio del dispositivo demo. El worker los lee con la configuración; si acabas de cargar la demo, espera unos segundos. Si responde `No encontrado`, espera y vuelve a lanzarlo.

`open` crea **Puerta abierta**, severidad media. No sale aviso.

`alarm` crea **Humo**, severidad crítica, en Detector de humo. Abajo a la derecha aparece un aviso **CRÍTICO**. Dura unos seis segundos. Al pulsarlo abre el evento.

Di: "La puerta y el humo entran por el dispositivo del sitio. El humo es crítico y el panel lo muestra al momento."

Un segundo `open` o `alarm` del mismo sensor dentro de 60 segundos no crea otro evento.

## 4:10 — Senti

Pantalla: Senti.

1. Abre el menú + y pulsa "¿Cuántas intrusiones hubo esta semana?". Llega al momento, sin llamar al modelo. Di: "Esta respuesta sale de la base de la organización, no del modelo."
2. Escribe, con tus palabras, una pregunta que no sea una de las tres sugeridas. Por ejemplo: "¿Cuál fue el evento más grave de ayer y qué cámaras están habilitadas?". Espera la respuesta. Di: "Esto sí pasa por Gemini. Solo puede usar herramientas fijas, de esta organización. No escribe SQL."
3. Escribe: "Marca la intrusión más reciente de Acceso norte como falso positivo." No confirmes todavía. Di: "Todavía no cambió nada." Pulsa Confirmar. Abre Eventos y enseña esa fila.

Si Gemini responde que hay demasiadas consultas, di que el nivel gratuito tiene cupo y que la pregunta de la semana no dependía de eso.

## 5:00 — En vivo

Pantalla: Cámaras. Abre Acceso norte. Pulsa **Iniciar análisis**.

Di: "Esto no pasa por la nube. El navegador habla con el worker en la red del sitio, con un permiso que caduca a los cinco minutos. Los recuadros y la palabra Persona son el análisis en ese momento. Debajo del video están los últimos eventos de esta cámara."

Mientras arranca, la pantalla dice Conectando… y el reproductor vuelve a pedir el stream hasta que llegan cuadros. Enseña los recuadros siguiendo a las personas. El indicador Analizando queda en una esquina del video y muestra los cuadros por segundo y cuántas personas hay en el cuadro. En la cuadrícula, la miniatura solo se abre si la cámara está activa y la tarjeta está a la vista. Si la cámara está apagada, la pantalla dice Cámara sin señal y el worker no gasta CPU codificando el stream.

Salir de la página no apaga el análisis: sigue solo si lo dejaste encendido. Antes de cerrar, pulsa **Detener análisis**. Cada vuelta cuenta minutos y puede crear otro evento.
