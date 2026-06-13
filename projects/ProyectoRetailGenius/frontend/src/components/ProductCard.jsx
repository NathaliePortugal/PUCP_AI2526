const CATEGORY_LABEL = {
  electronica:  'TV',
  computadores: 'PC',
  celulares:    'CEL',
  audio:        'AUD',
  hogar:        'HOG',
  gaming:       'GAM',
  mascotas:     'PET',
}

function Stars({ rating }) {
  const full = Math.floor(rating)
  const half = rating - full >= 0.5
  const empty = 5 - full - (half ? 1 : 0)
  return (
    <span className="product-card__stars">
      {'★'.repeat(full)}{half ? '½' : ''}{'☆'.repeat(empty)} {rating.toFixed(1)}
    </span>
  )
}

export default function ProductCard({ product }) {
  const label = CATEGORY_LABEL[product.category] || '?'
  return (
    <div className="product-card">
      {product.image_url
        ? <img className="product-card__img" src={product.image_url} alt={product.name} />
        : <div className="product-card__img">{label}</div>
      }
      <div className="product-card__brand">{product.brand}</div>
      <h3 className="product-card__name">{product.name}</h3>
      <Stars rating={product.rating} />
      <div className="product-card__price">
        ${product.price_usd.toFixed(2)} <small>USD</small>
      </div>
      {product.in_stock
        ? <button className="btn-cart">Agregar al carrito</button>
        : <p className="product-card__out-of-stock">Sin stock</p>
      }
    </div>
  )
}
