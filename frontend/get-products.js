const API_URL = "http://localhost:5001"; // URL del backend

const categorySelect = document.getElementById("categorySelect");
const subcategorySelect = document.getElementById("subcategorySelect");
const loadingSpinnerCategories = document.getElementById("loadingSpinnerCategories");
const loadingSpinnerSubCategories = document.getElementById("loadingSpinnerCategories");

// Eventos
categorySelect.addEventListener("change", handleCategoryChange);
subcategorySelect.addEventListener("change", loadProducts);
document.addEventListener("DOMContentLoaded", loadCategories);

// Cargar las categorías al iniciar la página
async function loadCategories() {
  try {
    loadingSpinnerCategories.classList.remove("d-none");
    categorySelect.disabled = true;

    const response = await fetch(`${API_URL}/api/categories/`);
    if (!response.ok) throw new Error("Error al cargar categorías");

    const categories = await response.json();
    categorySelect.innerHTML = "<option value=''>Seleccione una categoría</option>";
    subcategorySelect.innerHTML = "<option value=''>Seleccione una categoría primero...</option>";

    categories.forEach((category) => {
      const option = document.createElement("option");
      option.value = category.id;
      option.textContent = category.title;
      categorySelect.appendChild(option);
    });
  } catch (error) {
    console.error("Error al cargar categorías:", error);
  } finally {
    loadingSpinnerCategories.classList.add("d-none");
    categorySelect.disabled = false;
  }
}

// Manejar la selección de categoría para cargar subcategorías
async function handleCategoryChange() {
  const selectedCategoryId = categorySelect.value;

  if (!selectedCategoryId) {
    subcategorySelect.innerHTML = "<option value=''>Seleccione una categoría primero...</option>";
    subcategorySelect.disabled = true;
    return;
  }

  try {
    subcategorySelect.disabled = true;
    loadingSpinnerSubcategories.classList.remove("d-none"); // Asegurarse de que esta variable esté definida y sea correcta

    const response = await fetch(`${API_URL}/api/categories/${selectedCategoryId}`);
    if (!response.ok) throw new Error("Error al cargar subcategorías");

    const subcategories = await response.json();

    if (subcategories && Array.isArray(subcategories.childs)) {
      const childs = subcategories.childs;
      subcategorySelect.innerHTML = "<option value=''>Seleccione una subcategoría</option>";

      childs.forEach((subcategory) => {
        if (subcategory && subcategory.id && subcategory.title) {
          const option = document.createElement("option");
          option.value = subcategory.id;
          option.textContent = subcategory.title;
          subcategorySelect.appendChild(option);
        } else {
          console.warn("Subcategoría con formato inesperado:", subcategory);
        }
      });

      subcategorySelect.disabled = false;
    } else {
      console.error("El formato de subcategorías no es válido o no contiene la propiedad 'childs'.", subcategories);
      subcategorySelect.innerHTML = "<option value=''>Seleccione una categoría primero...</option>";
      subcategorySelect.disabled = true;
    }
  } catch (error) {
    console.error("Error al cargar subcategorías:", error);
  } finally {
    loadingSpinnerSubcategories.classList.add("d-none"); // Misma corrección aquí
  }
}


// Cargar los productos al seleccionar una subcategoría
async function loadProducts() {
  const categoryId = categorySelect.value; // Obtén el valor seleccionado de categoría
  const subcategoryId = subcategorySelect.value; // Obtén el valor seleccionado de subcategoría

  if (!categoryId || !subcategoryId) {
    alert("Por favor selecciona una categoría y una subcategoría");
    return;
  }

  try {
    const response = await fetch(`${API_URL}/api/categories/${categoryId}/${subcategoryId}`);
    if (!response.ok) {
      throw new Error(`Error al cargar productos: ${response.status} ${response.statusText}`);
    }

    const data = await response.json();

    // Validación adicional para asegurar que la respuesta contiene la estructura esperada
    if (!data || !Array.isArray(data.childs) || !data.childs[0] || !Array.isArray(data.childs[0].products)) {
      throw new Error("La estructura de datos de los productos es inesperada.");
    }

    const products = data.childs[0].products;
    renderProductsTable(products); // Renderiza los productos en la tabla
  } catch (error) {
    console.error("Error al cargar productos:", error);
    alert("Hubo un problema al cargar los productos. Por favor intenta nuevamente.");
  }
}

// Renderizar los productos en una tabla con DataTables
function renderProductsTable(products) {
  const tableContainer = document.getElementById("productsTable");

  if (products.length === 0) {
    tableContainer.innerHTML = "<p>No se encontraron productos para esta subcategoría.</p>";
    return;
  }

// Generar HTML para la tabla
tableContainer.innerHTML = `
<table id="productsDataTable" class="table table-bordered table-striped align-middle">
  <thead>
    <tr>
      <th>ID</th>
      <th>Imagen</th>
      <th>Título</th>
      <th>Descripción</th>
      <th>Detalle</th>
    </tr>
  </thead>
  <tbody>
    ${products
      .map(
        (product) => {
          const smallImage = product.images?.find(image => image.variations?.some(variation => variation.size === "SMALL"))?.variations.find(variation => variation.size === "SMALL")?.url || "https://via.placeholder.com/50";
          return `
          <tr>
            <td>${product.id}</td>
            <td><img src="${smallImage}" alt="${product.title}" style="width: 50px; height: auto;"></td>
            <td>${product.title}</td>
            <td>${product.description}</td>
            <td class="text-center">
              <i class="fas fa-info-circle text-info detail-icon" 
                title="Ver detalles"
                aria-label="Ver detalles"
                data-id="${product.id}" 
                role="button"
                tabindex="0"
                onclick="showProductDetails('${product.id}')"></i>
            </td>
          </tr>
        `;
        }
      )
      .join("")}
  </tbody>
</table>`;


// Agregar DataTables
$("#productsDataTable").DataTable({
paging: true,
searching: true,
ordering: true,
info: true,
autoWidth: false,
language: {
  url: "https://cdn.datatables.net/plug-ins/1.13.6/i18n/es-ES.json",
}});
}


// Función para mostrar detalles de un producto
async function showProductDetails(productId) {
  try {
    // Seleccionar el ícono clickeado
    const detailIcon = document.querySelector(`.detail-icon[data-id="${productId}"]`);
    if (detailIcon) {
      // Deshabilitar el ícono y mostrar el spinner
      detailIcon.classList.remove("fa-info-circle");
      detailIcon.classList.add("fa-spinner", "fa-spin");
      detailIcon.style.pointerEvents = "none"; // Evitar clics adicionales
    }

    console.log(`Cargando detalles del producto con ID: ${productId}`);
    const response = await fetch(`${API_URL}/api/product/${productId}`);
    if (!response.ok) throw new Error("Error al cargar producto");

    const producto = await response.json();
    
    console.log(`Detalles del producto:`, producto);

    // Filtrar imágenes que no sean íconos
    const images = producto.images
      ?.flatMap(image => image.variations)
      .map(variation => variation.url) || [];

    // Generar contenido del carrusel
    const carousel = images.length > 0 ? `
    <div id="productCarousel" class="carousel slide" data-bs-ride="carousel">
      <div class="carousel-inner">
        ${images.map((url, index) => `
          <div class="carousel-item ${index === 0 ? 'active' : ''}">
            <img src="${url}" class="d-block w-100" alt="Imagen del producto">
          </div>
        `).join('')}
      </div>
      <button class="carousel-control-prev" type="button" data-bs-target="#productCarousel" data-bs-slide="prev">
        <span class="carousel-control-prev-icon" aria-hidden="true" style="background-color: black;"></span>
        <span class="visually-hidden">Anterior</span>
      </button>
      <button class="carousel-control-next" type="button" data-bs-target="#productCarousel" data-bs-slide="next">
        <span class="carousel-control-next-icon" aria-hidden="true" style="background-color: black;"></span>
        <span class="visually-hidden">Siguiente</span>
      </button>
    </div>
    ` : '<p>No hay imágenes disponibles.</p>';

    // Obtener datos adicionales
    const availability = producto.availability?.availability ? "En stock" : "Agotado";
    const brand = producto.extraData?.brand || "No especificada";
    const price = producto.extraData?.pvp_ecommerce || "No disponible";
    const sku = producto.sku || "No disponible";
    const barcode = producto.extraData?.barcode || "No disponible";
    const currency = producto.extraData?.currency || "No especificada";

    // Mostrar el modal con toda la información
    Swal.fire({
      title: producto.title,
      html: `
        <div style="max-width: 800px; margin: 0 auto; text-align: left;">
          ${carousel}
          <p>${DOMPurify.sanitize(producto.body)}</p>
          <ul style="list-style: none; padding: 0;">
            <li><strong>Disponibilidad:</strong> ${availability}</li>
            <li><strong>Marca:</strong> ${brand}</li>
            <li><strong>Costo:</strong> ${currency} ${price}</li>
            <li><strong>SKU:</strong> ${sku}</li>
            <li><strong>Código de barras:</strong> ${barcode}</li>
            <li><strong>Moneda:</strong> ${currency}</li>
          </ul>
          <div class="text-center mt-4">
            <button id="sendToShopify" class="btn btn-primary">Enviar producto a Shopify</button>
          </div>
        </div>
      `,
      icon: "info",
      width: 800,
      customClass: {
        popup: 'swal-wide'
      },
      backdrop: 'rgba(0, 0, 0, 0.5)'
    });

    // Agregar evento al botón "Enviar producto a Shopify"
    document.getElementById("sendToShopify").addEventListener("click", async () => {
      // Mostrar spinner bloqueando la pantalla
      Swal.fire({
        title: 'Procesando...',
        text: 'Enviando producto a Shopify. Por favor espera.',
        allowOutsideClick: false,
        allowEscapeKey: false,
        didOpen: () => {
          Swal.showLoading();
        }
      });

      try {
        const shopifyResponse = await fetch(`${API_URL}/api/shopify/create_product`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify(producto)
        });

        if (shopifyResponse.ok) {
          Swal.fire({
            title: "Éxito",
            text: "Producto enviado a Shopify correctamente.",
            icon: "success"
          });
        } else {
          const errorData = await shopifyResponse.json();
          Swal.fire({
            title: "Error",
            text: `No se pudo enviar el producto a Shopify: ${errorData.error || "Error desconocido"}`,
            icon: "error"
          });
        }
      } catch (error) {
        Swal.fire({
          title: "Error",
          text: "Ocurrió un error al intentar enviar el producto a Shopify.",
          icon: "error"
        });
      }
    });
  } catch (error) {
    console.error("Error al cargar los detalles del producto:", error);
    Swal.fire({
      title: "Error",
      text: "No se pudieron cargar los detalles del producto. Por favor, intenta nuevamente.",
      icon: "error",
    });
  } finally {
    // Restaurar el ícono original
    const detailIcon = document.querySelector(`.detail-icon[data-id="${productId}"]`);
    if (detailIcon) {
      detailIcon.classList.remove("fa-spinner", "fa-spin");
      detailIcon.classList.add("fa-info-circle");
      detailIcon.style.pointerEvents = "auto"; // Habilitar clics nuevamente
    }
  }
}











