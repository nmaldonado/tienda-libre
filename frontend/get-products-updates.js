const API_URL = "https://panel.tiendalibre.com.uy"; // URL del backend
let productTable;

// Asignar la fecha de hoy al input datePicker al cargar la página
document.addEventListener('DOMContentLoaded', () => {
    const today = dayjs().format('YYYY-MM-DD'); // Formato compatible con input date
    const datePicker = document.getElementById('datePicker');
    datePicker.value = today;
    loadData(); // Llamar a la función para cargar los datos al iniciar
  });

// Evento para cargar datos al cambiar la fecha
document.getElementById("datePicker").addEventListener("change", loadData);

//spinner
const loadingSpinnerProducts = document.getElementById("loadingSpinnerProducts");

/**
 * Función `loadData`
 * 
 * Descripción:
 * Esta función obtiene datos desde un servidor en función de una fecha seleccionada. 
 * Si hay datos disponibles, los muestra en una tabla; de lo contrario, limpia la tabla 
 * y muestra un mensaje de error.
 * 
 * Parámetros:
 * - No recibe parámetros directamente. Obtiene la fecha seleccionada del elemento HTML con el ID `datePicker`.
 * 
 * Flujo de ejecución:
 * 1. Obtiene el valor del campo `datePicker`. Si no hay un valor seleccionado, utiliza la fecha actual como predeterminada.
 * 2. Formatea la fecha al formato `DD_MM_YYYY` usando Day.js.
 * 3. Construye la URL de la API, añadiendo la fecha como parámetro de consulta.
 * 4. Realiza una solicitud `fetch` al servidor.
 * 5. Si la respuesta es exitosa:
 *    - Procesa los datos y los envía a la función `renderTable` para renderizar la tabla.
 *    - Oculta cualquier mensaje de error previo.
 * 6. Si la solicitud falla o no hay datos:
 *    - Limpia la tabla llamando a `clearTable`.
 *    - Muestra un mensaje de error llamando a `showErrorMessage`.
 * 
 * Retorno:
 * - Esta función no devuelve valores explícitos (`void`).
 * - Modifica dinámicamente el DOM de la página.
 * 
 * Dependencias:
 * - Elementos HTML:
 *   - `#datePicker`: Input de tipo fecha que contiene la fecha seleccionada.
 *   - `#errorMessage`: Contenedor donde se muestra un mensaje de error.
 * - Funciones auxiliares:
 *   - `renderTable(data)`: Renderiza los datos obtenidos en una tabla.
 *   - `clearTable()`: Limpia la tabla existente.
 *   - `showErrorMessage(message)`: Muestra un mensaje de error en pantalla.
 * - Bibliotecas:
 *   - `Day.js`: Para manipular y formatear la fecha.
 *   - `Fetch API`: Para realizar la solicitud HTTP al backend.
 * 
 * Ejemplo de uso:
 * - Supongamos que el usuario selecciona `12/31/2023` en el campo de fecha:
 *   1. El valor de `#datePicker` será `"2023-12-31"`.
 *   2. La función formatea esta fecha como `31_12_2023`.
 *   3. Realiza la solicitud a la API: `http://46.202.150.190:5000/data?date=31_12_2023`.
 *   4. Si hay datos disponibles, se renderizan en la tabla.
 *   5. Si no hay datos, se limpia la tabla y se muestra un mensaje: "No se encontraron datos para esta fecha."
 * 
 * Notas:
 * - Asegúrate de que la API retorne datos en formato JSON válido.
 * - La función depende de otros métodos auxiliares (`clearTable`, `renderTable`, `showErrorMessage`) para manejar el DOM.
 * - El ID del campo de fecha (`datePicker`) debe coincidir con el usado en el HTML.
 */

async function loadData() {
  const loadingSpinnerProducts = document.getElementById("loadingSpinnerProducts");
  const productTable = document.getElementById("productTable");
  const errorMessage = document.getElementById("errorMessage");

  // Establecer velocidad de animación
  productTable.style.setProperty("--animate-duration", "0.3s");

  loadingSpinnerProducts.classList.remove("d-none");

  const dateInput = document.getElementById("datePicker").value;
  const date = dateInput ? dayjs(dateInput).format('DD_MM_YYYY') : dayjs().format('DD_MM_YYYY');
  const url = `${API_URL}/api/data?date=${date}`;

  try {
    const response = await fetch(url);

    if (!response.ok) {
      throw new Error("No se encontraron datos para esta fecha.");
    }

    const data = await response.json();

    errorMessage.classList.add("d-none"); // Ocultar mensaje de error

    // Animar la aparición de la tabla con datos nuevos
    if (productTable.classList.contains("d-none")) {
      productTable.classList.remove("d-none", "animate__fadeOut");
      productTable.classList.add("animate__fadeIn");
    }

    renderTable(data); // Renderizar la tabla con datos nuevos
  } catch (error) {
    console.error(error);

    // Animar la desaparición de la tabla si no hay datos
    productTable.classList.remove("animate__fadeIn");
    productTable.classList.add("animate__fadeOut");

    productTable.addEventListener(
      "animationend",
      () => {
        if (productTable.classList.contains("animate__fadeOut")) {
          productTable.classList.add("d-none"); // Ocultar la tabla
          clearTable(); // Limpia la tabla si no hay datos disponibles
        }
      },
      { once: true }
    );

    showErrorMessage(error.message); // Muestra un mensaje informativo
  } finally {
    loadingSpinnerProducts.classList.add("d-none");
  }
}


// Limpia la tabla y destruye la instancia de DataTable
function clearTable() {
  if (productTable) {
    productTable.clear().destroy();
    productTable = null; // Reiniciar la referencia de DataTable
  }
  const tableBody = $('#productTable tbody');
  tableBody.empty();

    // Ocultar el mensaje dinámico
    const updateMessage = document.getElementById("updateMessage");
    updateMessage.classList.add("d-none");
}

// Muestra un mensaje de error
function showErrorMessage(message) {
  const errorMessageDiv = document.getElementById("errorMessage");
  errorMessageDiv.textContent = message;
  errorMessageDiv.classList.remove("d-none");
}

/**
 * Función `renderTable`
 *
 * Descripción:
 * Renderiza los datos de productos en una tabla HTML y aplica el plugin DataTables para la funcionalidad de paginación,
 * búsqueda, ordenamiento y más.
 * 
 * Parámetros:
 * - `data` (Array): Un array de objetos que representan los productos. Cada objeto debe contener propiedades como
 *   `ID`, `Marca`, `Categoria`, `Titulo`, `Descripcion`, `Stock`, `Cambios`, y `Image_URLs`.
 * 
 * Flujo de ejecución:
 * 1. Limpia cualquier instancia previa de la tabla llamando a `clearTable`.
 * 2. Itera sobre los datos del array `data` para construir dinámicamente filas de la tabla:
 *    - Procesa las URLs de imágenes (`Image_URLs`) para seleccionar una imagen principal.
 *    - Genera un identificador único (`productId`) para cada fila.
 *    - Inserta las filas en el cuerpo de la tabla HTML.
 *    - Almacena el producto completo como un atributo `dataset` del elemento `document.body`.
 * 3. Inicializa una nueva instancia de DataTable en el elemento de la tabla HTML.
 * 
 * Retorno:
 * - Esta función no retorna ningún valor explícito (`void`).
 * - Modifica el DOM al actualizar el contenido de la tabla y sus funcionalidades.
 * 
 * Dependencias:
 * - Función `clearTable()`: Limpia cualquier tabla previa y destruye la instancia de DataTable si existe.
 * - Biblioteca `jQuery`: Para manipulación del DOM y selección de elementos.
 * - Plugin `DataTables`: Para agregar funcionalidades avanzadas a la tabla.
 * - Elementos HTML:
 *   - `#productTable`: La tabla donde se renderizan los productos.
 * - Propiedad `Image_URLs`: Una lista separada por comas con URLs de imágenes de cada producto.
 * 
 * Ejemplo de uso:
 * ```javascript
 * const productos = [
 *   {
 *     ID: "001",
 *     Marca: "Marca A",
 *     Categoria: "Electrónica",
 *     Titulo: "Producto 1",
 *     Descripcion: "Descripción del producto 1",
 *     Stock: 100,
 *     Cambios: 2,
 *     Image_URLs: "https://example.com/img1.jpg, https://example.com/img2.jpg"
 *   },
 *   // Más productos...
 * ];
 * renderTable(productos);
 * ```
 * 
 * Notas:
 * - Asegúrate de que `data` contenga los campos necesarios para evitar errores.
 * - El plugin DataTables se inicializa en cada llamada a esta función, destruyendo cualquier instancia previa.
 * - Las imágenes se seleccionan basándose en la presencia de "ICO" o la primera URL disponible en `Image_URLs`.
 */
function renderTable(data) {
  clearTable(); // Asegurarse de limpiar cualquier tabla previa

  const tableBody = $('#productTable tbody');
  tableBody.empty();

  data.forEach((row) => {
    const imageUrlsArray = row.Image_URLs
      .split(',')
      .map(url => url.trim().replace(/['"]/g, '')); // Quita todas las comillas simples y dobles

    const imageUrl = imageUrlsArray.find(url => url.includes("ICO") || url.includes("ico")) || imageUrlsArray[0] || "#";

    const productId = `product-${row.ID}`;

    tableBody.append(`
        <tr>
            <td><img src="${imageUrl}" alt="Producto" style="width: 150px; height: auto;"></td>
            <td>${row.ID || "-"}</td>
            <td>${row.Brand || "-"}</td>
            <td>${row.Category || "-"}</td>
            <td>${row.Title || "-"}</td>
            <td>${row.Description || "-"}</td>
            <td>${row.Stock || "0"}</td>
            <td>${row.Changes || "-"}</td>
            <td style="text-align: center; vertical-align: middle;">
              <button class="btn" style="background-color: rgb(13, 110, 253); color: white;" onclick='showDetails("${productId}")'>
                <i class="bi bi-info-circle"></i>
              </button>
            </td>
        </tr>
    `);

    document.body.dataset[productId] = JSON.stringify(row);
  });

  // Crear una nueva instancia de DataTable
  productTable = $('#productTable').DataTable({
    paging: true,
    searching: true,
    ordering: true,
    info: true,
    autoWidth: false,
    language: {
      url: "https://cdn.datatables.net/plug-ins/1.13.6/i18n/es-ES.json"
    }
  });


    // Actualizar el mensaje dinámico
    const updateMessage = document.getElementById("updateMessage");
    if (data.length > 0) {
      updateMessage.textContent = `${data.length} artículos con cambios`;
      updateMessage.classList.remove("d-none");
    } else {
      updateMessage.classList.add("d-none");
    }
}

/**
 * Función `showDetails`
 * 
 * Descripción:
 * Muestra un modal con información detallada de un producto seleccionado, incluyendo imágenes, detalles principales
 * y cuerpo adicional del producto. Utiliza la librería SweetAlert2 para el modal y LightGallery para la galería de imágenes.
 * 
 * Parámetros:
 * - `productId` (String): El identificador único del producto. Este ID se utiliza para recuperar los detalles del producto
 *   almacenados previamente en `document.body.dataset`.
 * 
 * Flujo de ejecución:
 * 1. Recupera el JSON del producto desde el atributo `dataset` del elemento `document.body` usando el `productId`.
 * 2. Convierte el JSON en un objeto de JavaScript.
 * 3. Sanitiza el campo `Body` del producto usando `DOMPurify` para prevenir inyecciones de código.
 * 4. Genera una galería de imágenes basándose en el campo `Image_URLs` del producto:
 *    - Limpia y procesa las URLs.
 *    - Construye un contenedor de galería con imágenes.
 * 5. Genera el contenido del modal incluyendo detalles como el título, marca, categoría, stock, costo, y cambios.
 * 6. Muestra el modal con SweetAlert2 y configura la galería de imágenes usando LightGallery.
 * 
 * Retorno:
 * - Esta función no devuelve valores explícitos (`void`).
 * - Modifica dinámicamente el DOM para mostrar un modal con los detalles del producto.
 * 
 * Dependencias:
 * - Librerías:
 *   - `DOMPurify`: Para sanitizar el contenido del campo `Body`.
 *   - `SweetAlert2`: Para mostrar el modal.
 *   - `LightGallery`: Para mostrar las imágenes como una galería interactiva.
 * - Elementos HTML:
 *   - `document.body.dataset`: Contiene los detalles del producto en formato JSON.
 *   - `#imageGallery`: Contenedor dinámico generado para las imágenes del producto.
 * 
 * Ejemplo de uso:
 * Supongamos que `productId` es `"product-001"`:
 * ```javascript
 * showDetails("product-001");
 * ```
 * Flujo:
 * 1. Recupera el JSON del producto desde `document.body.dataset["product-001"]`.
 * 2. Genera un modal con los siguientes detalles:
 *    - Título: "Producto A"
 *    - Marca: "Marca X"
 *    - Categoría: "Electrónica"
 *    - Stock: "10"
 *    - Imágenes: Se muestran como una galería interactiva.
 * 3. Muestra el modal con SweetAlert2 y LightGallery.
 * 
 * Notas:
 * - Asegúrate de que el `productId` exista en `document.body.dataset` para evitar errores.
 * - `Image_URLs` debe ser una lista separada por comas de URLs de imágenes válidas.
 * - Configura correctamente las librerías SweetAlert2 y LightGallery antes de llamar a esta función.
 */
function showDetails(productId) {
  const productJson = document.body.dataset[productId];
  const product = JSON.parse(productJson);

  const sanitizedBody = DOMPurify.sanitize(product.Body || "");

  const imageUrlsArray = product.Image_URLs
    ? product.Image_URLs.split(',')
        .map(url => url.trim().replace(/['"]/g, ''))
    : [];

  const imageGallery = imageUrlsArray.length
    ? `<div id="imageGallery" style="display: flex; gap: 10px; flex-wrap: wrap; margin-top: 15px;">
          ${imageUrlsArray
            .map(
              url =>
                `<a href="${url}" data-lg-size="1600-900">
                   <img src="${url}" alt="Imagen del Producto" style="width: 100px; height: auto; border: 1px solid #ddd; border-radius: 5px;">
                 </a>`
            )
            .join('')}
       </div>`
    : '<p style="margin-top: 15px;">No hay imágenes disponibles.</p>';

  const productDetails = `
      <div style="text-align: center; margin-bottom: 20px;">
          <h5 style="font-weight: bold;">${product.Title || "Sin Título"}</h5>
          <p style="font-size: 24px; color: gray;">${product.Brand || "Sin Marca"}</p>
      </div>
      <div style="margin-bottom: 15px;">
          <p><strong>Descripción:</strong></p>
          <p>${product.Description || "No disponible"}</p>
      </div>
      <div style="display: flex; justify-content: space-between; margin-bottom: 15px;">
          <p><strong>Categoría:</strong> ${product.Category || "N/A"}</p>
      </div>
      <div style="display: flex; justify-content: space-between; margin-bottom: 15px;">
        <p style="font-size: ${product.Stock === 0 ? '2em' : 'inherit'}; color: ${product.Stock === 0 ? 'red' : 'inherit'};">
          <strong>Stock:</strong> ${product.Stock || "0"}
        </p>
        <p><strong>Moneda:</strong> ${product.Currency || "N/A"}</p>
        <p><strong>Costo:</strong> ${product.Price || "0"}</p>
        <p><strong>Cambios:</strong> ${product.Changes || "0"}</p>
      </div>        
      <div style="border-top: 1px solid #ddd; padding-top: 15px; margin-top: 15px;">
          <p><strong>Detalles adicionales:</strong></p>
          <div>${sanitizedBody}</div>
      </div>
      ${imageGallery}
  `;

  Swal.fire({
    title: `${product.Titulo || "Detalle del Producto"}`,
    html: productDetails,
    width: '60%',
    showCloseButton: true,
    focusConfirm: false,
    confirmButtonText: 'Cerrar',
    didOpen: () => {
      lightGallery(document.getElementById('imageGallery'), {
        plugins: [lgZoom],
        speed: 500,
        download: false,
      });
    },
  });
}

// Cargar la barra de navegación desde el archivo navbar.html
document.addEventListener("DOMContentLoaded", function () {
  fetch("navbar.html")
    .then(response => response.text())
    .then(data => {
      document.getElementById("navbar").innerHTML = data;
    })
    .catch(error => console.error("Error cargando la barra de navegación:", error));
});


