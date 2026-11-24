# SimpleSave: guía rápida

SimpleSave guarda tu escena por versiones y hace copias automáticas para que no pierdas trabajo.

## Guardar versión

- Pulsa `Ctrl+Alt+S` (en Mac `⌘+Alt+S`), o *SimpleSave › Guardar versión*, o el botón azul del panel.
- Escribe en una línea qué has hecho («brazos», «UVs del casco»). Es opcional, pero dentro de una semana lo agradecerás.
- Cada vez se crea un archivo nuevo: `robot_v001.ma`, `robot_v002.ma`… Nunca se pisa uno anterior.
- `Ctrl+S` sigue funcionando como siempre: guarda encima de la versión que tienes abierta.
- Guarda versión cada vez que termines una parte. Si pasan 30 minutos sin hacerlo, verás un aviso en el visor.

## La primera vez

Si la escena no tiene nombre, SimpleSave te pide los datos (el nombre de la escena y lo que haya pedido tu profesor).
Escribe con normalidad: las tildes, la ñ y los espacios se corrigen solos y ves el nombre final antes de guardar.

## El panel

*SimpleSave › Panel de versiones* abre la lista de versiones con su miniatura y su nota.

- **Abrir**: abre esa versión.
- **Restaurar**: copia una versión antigua como versión nueva y la abre. La que tenías sigue ahí.
- Clic derecho en una versión: editar la nota, marcarla como importante, mostrarla en la carpeta.
- El punto naranja arriba significa que tienes cambios sin guardar en una versión.

## Si Maya se cierra

SimpleSave hace una copia automática cada 5 minutos si has cambiado algo. Al volver a abrir Maya o la escena,
si hay una copia más reciente que tu última versión, te pregunta si quieres **recuperarla**. Se guarda como versión
nueva, así que no pierdes nada aunque te equivoques. También puedes buscarla tú en *SimpleSave › Recuperar trabajo…*.

## Entregar

1. Guarda una última versión con una nota tipo «entrega».
2. Pulsa **Entregar** en el panel. En la carpeta `entregas` del proyecto aparecen `<nombre>_entrega.ma` y un `.zip`
   con la escena y sus texturas.
3. Entrega el `.zip`. Si el aviso dice que alguna textura estaba fuera del proyecto, muévela a `sourceimages` y
   vuelve a entregar.

## Copia en el USB o en la nube

En la pestaña **Ajustes**, activa *Copiar cada versión también a otra carpeta* y elige la carpeta del USB, Drive u
OneDrive. Si el USB no está conectado, la versión se guarda igual en el ordenador y el panel te avisa.
