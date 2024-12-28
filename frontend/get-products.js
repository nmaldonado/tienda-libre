const API_URL = "http://46.202.150.190:5001"; // URL del backend

const categorySelect = document.getElementById("categorySelect");
const subcategorySelect = document.getElementById("subcategorySelect");
const loadingSpinnerCategories = document.getElementById("loadingSpinnerCategories");
const loadingSpinnerSubCategories = document.getElementById("loadingSpinnerSubCategories");

// Eventos
categorySelect.addEventListener("change", handleCategoryChange);
subcategorySelect.addEventListener("change", loadProducts);
document.addEventListener("DOMContentLoaded", loadCategories);

/**
 * Carga las categorías disponibles desde el backend y las muestra en el selector.
 * - Realiza una solicitud GET al endpoint `/api/categories/`.
 * - Inserta las categorías recibidas en el selector de categorías.
 */
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

/**
 * Maneja el cambio en la selección de categoría para cargar sus subcategorías.
 * - Realiza una solicitud GET al endpoint `/api/categories/{categoryId}`.
 * - Actualiza el selector de subcategorías con las opciones disponibles.
 */
async function handleCategoryChange() {
  const selectedCategoryId = categorySelect.value;

  if (!selectedCategoryId) {
    subcategorySelect.innerHTML = "<option value=''>Seleccione una categoría primero...</option>";
    subcategorySelect.disabled = true;
    return;
  }

  try {
    subcategorySelect.disabled = true;
    loadingSpinnerSubcategories.classList.remove("d-none");

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
    loadingSpinnerSubcategories.classList.add("d-none");
  }
}

/**
 * Carga los productos disponibles para la categoría y subcategoría seleccionadas.
 * - Realiza una solicitud GET al endpoint `/api/categories/{categoryId}/{subcategoryId}`.
 * - Renderiza los productos obtenidos en una tabla.
 */
async function loadProducts() {
  const categoryId = categorySelect.value;
  const subcategoryId = subcategorySelect.value;

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
    renderProductsTable(products);
  } catch (error) {
    console.error("Error al cargar productos:", error);
    alert("Hubo un problema al cargar los productos. Por favor intenta nuevamente.");
  }
}

/**
 * Renderiza los productos en una tabla utilizando DataTables.
 * - Genera el HTML de una tabla con los productos recibidos.
 * - Aplica la funcionalidad de DataTables.
 */
function renderProductsTable(products) {
  const tableContainer = document.getElementById("productsTable");

  if (products.length === 0) {
    tableContainer.innerHTML = "<p>No se encontraron productos para esta subcategoría.</p>";
    return;
  }

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
      .map((product) => {
        const smallImage =
          product.images?.find((image) =>
            image.variations?.some((variation) => variation.size === "SMALL")
          )?.variations.find((variation) => variation.size === "SMALL")?.url || "https://via.placeholder.com/50";
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
      })
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
    },
  });
}

/**
 * Muestra los detalles de un producto en un modal.
 * - Realiza una solicitud GET al endpoint `/api/product/{productId}`.
 * - Muestra información detallada del producto y permite enviarlo a Shopify.
 */
async function showProductDetails(productId) {
  try {
    const detailIcon = document.querySelector(`.detail-icon[data-id="${productId}"]`);
    if (detailIcon) {
      detailIcon.classList.remove("fa-info-circle");
      detailIcon.classList.add("fa-spinner", "fa-spin");
      detailIcon.style.pointerEvents = "none";
    }

    console.log(`Cargando detalles del producto con ID: ${productId}`);
    const response = await fetch(`${API_URL}/api/product/${productId}`);
    if (!response.ok) throw new Error("Error al cargar producto");

    const producto = await response.json();
    console.log(`Detalles del producto:`, producto);

    const images = producto.images?.flatMap(image => image.variations).map(variation => variation.url) || [];

    const availability = producto.availability?.availability ? "En stock" : "Agotado";
    const brand = producto.extraData?.brand || "No especificada";
    const price = producto.extraData?.pvp_ecommerce || "No disponible";

    Swal.fire({
      title: producto.title,
      html: `<p>Detalles...</p>`, // Resumido por espacio
    });
  } catch (error) {
    console.error("Error al cargar los detalles del producto:", error);
    Swal.fire({
      title: "Error",
      text: "No se pudieron cargar los detalles del producto.",
      icon: "error",
    });
  }
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
