import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import urllib.parse
import csv
from datetime import datetime
import matplotlib.pyplot as plt
import numpy as np
import os

BOT_TOKEN = "7766831416:AAHZIlb1L8oQ0IwDX9-YZywkhgrMTkbrPRU"


def guardar_en_csv(estaciones, tipo_combustible, archivo='estaciones_combustible.csv'):
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    archivo_existe = os.path.isfile(archivo)

    with open(archivo, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)

        # Escribir encabezado si el archivo es nuevo
        if not archivo_existe:
            writer.writerow(["Fecha y Hora", "Tipo Combustible", "Nombre Estación", "Dirección", "Localidad", "Precio", "Latitud", "Longitud"])

        for e in estaciones:
            if tipo_combustible == "Gasolina95":
                precio = e.get("Gasolina95")
            else:
                precio = e.get("Diesel")

            writer.writerow([
                ahora,
                tipo_combustible,
                e.get("nombreEstacion"),
                e.get("direccion"),
                e.get("localidad"),
                precio,
                e.get("latitud"),
                e.get("longitud")
            ])

def mostrar_grafica_top5(top_gasolina, top_diesel, output_path="grafica_combustibles.png"):
    def nombres_con_direccion(estaciones):
        return [f"{e.get('nombreEstacion')} - {e.get('direccion')}" for e in estaciones]

    nombres_gasolina = nombres_con_direccion(top_gasolina)
    nombres_diesel = nombres_con_direccion(top_diesel)

    precios_gasolina = [e.get("Gasolina95") for e in top_gasolina]
    precios_diesel = [e.get("Diesel") for e in top_diesel]

    x = np.arange(len(top_gasolina))
    ancho = 0.35

    plt.figure(figsize=(14, 6))
    plt.bar(x - ancho/2, precios_gasolina, width=ancho, label="Gasolina 95", color='blue')
    plt.bar(x + ancho/2, precios_diesel, width=ancho, label="Diésel", color='orange')

    etiquetas = [f"{g}\n{d}" for g, d in zip(nombres_gasolina, nombres_diesel)]
    plt.xticks(x, etiquetas, rotation=45, ha='right')

    plt.ylabel("Precio (€)")
    plt.title("Top 5 precios más baratos - Gasolina 95 y Diésel")

    # Definir ticks manuales según tu solicitud
    ticks = [0, 0.5, 1, 1.2, 1.3, 1.4, 1.5, 1.6]
    plt.yticks(ticks)

    # Limitar rango para que sea visible todo lo que pides
    plt.ylim(0, 1.6)

    plt.legend()
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()


def get_coords_from_city(ciudad):
    ciudad_encoded = urllib.parse.quote(ciudad)
    url = f"https://nominatim.openstreetmap.org/search?format=json&q={ciudad_encoded}&limit=1"

    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    
    if response.status_code != 200:
        return None

    data = response.json()
    if not data:
        return None

    lat = data[0]['lat']
    lon = data[0]['lon']
    return (lat, lon)


def getEstaciones(ciudad):
    coords = get_coords_from_city(ciudad)
    if not coords:
        return None, f"❌ No se encontró la ciudad '{ciudad}'. Asegúrate de escribirla correctamente."

    lat, lon = coords
    url = f"https://api.precioil.es/estaciones/radio?latitud={lat}&longitud={lon}&radio=20&pagina=1&limite=50"

    response = requests.get(url)
    if response.status_code != 200:
        return None, "⚠️ Error al obtener los datos de las estaciones."

    estaciones = response.json()
    gasolina_estaciones = [e for e in estaciones if e.get('Gasolina95') is not None]
    gasoil_estaciones = [e for e in estaciones if e.get('Diesel') is not None]

    gasolina_ordenadas = sorted(gasolina_estaciones, key=lambda x: x['Gasolina95'])
    gasoil_ordenadas = sorted(gasoil_estaciones, key=lambda x: x['Diesel'])

    top_5_gasolina = gasolina_ordenadas[:5]
    top_5_gasoil = gasoil_ordenadas[:5]

    guardar_en_csv(top_5_gasolina, "Gasolina95", 'historico_gasolina.csv')
    guardar_en_csv(top_5_gasoil, "Diesel", 'historico_gasoil.csv')

    # Generar gráfica como imagen
    output_image = f"grafica_{ciudad.lower().replace(' ', '_')}.png"
    mostrar_grafica_top5(top_5_gasolina, top_5_gasoil, output_image)

    mensaje = f"📍 *TOP 5 Gasolineras en {ciudad.title()}*\n\n⛽ *Gasolina 95:*\n"
    for e in top_5_gasolina:
        mensaje += f"• {e.get('nombreEstacion')} - {e.get('Gasolina95')} €/L\n  {e.get('direccion')} ({e.get('localidad')})\n\n"

    mensaje += "\n🛢️ *Diésel:*\n"
    for e in top_5_gasoil:
        mensaje += f"• {e.get('nombreEstacion')} - {e.get('Diesel')} €/L\n  {e.get('direccion')} ({e.get('localidad')})\n\n"

    return output_image, mensaje


# Comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("¡Hola! Usa /combustible seguido de una ciudad. Ejemplo:\n/combustible Madrid")


# Comando /combustible <ciudad>
async def combustible(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❗ Debes indicar una ciudad. Ejemplo: /combustible Valencia")
        return

    ciudad = " ".join(context.args)
    await update.message.reply_text(f"🔎 Buscando gasolineras en *{ciudad}*...", parse_mode="Markdown")

    imagen, mensaje = getEstaciones(ciudad)

    if mensaje.startswith("❌") or mensaje.startswith("⚠️"):
        await update.message.reply_text(mensaje, parse_mode="Markdown")
    else:
        # ✅ Primero envía el mensaje de texto bien formateado
        await update.message.reply_text(mensaje, parse_mode="Markdown")
        
        # ✅ Luego, si hay imagen, envíala correctamente
        if imagen and os.path.isfile(imagen):
            with open(imagen, "rb") as photo:
                await update.message.reply_photo(photo)
            os.remove(imagen)  # Opcional: borrar la imagen temporal



# MAIN
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("combustible", combustible))

    print("✅ Bot en marcha...")
    app.run_polling()
