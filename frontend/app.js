const API = '/api/v1';
let token = localStorage.getItem('orderflow_token') || '';
let user = JSON.parse(localStorage.getItem('orderflow_user') || 'null');
let registerMode = false;
const $ = (id) => document.getElementById(id);
const money = (value) => new Intl.NumberFormat('en-IN', {style:'currency', currency:'INR'}).format(Number(value || 0));
const authHeaders = () => token ? {'Authorization': `Bearer ${token}`} : {};
async function api(path, options={}) {
  const headers = {'Content-Type':'application/json', ...authHeaders(), ...(options.headers || {})};
  const response = await fetch(`${API}${path}`, {...options, headers});
  const data = response.status === 204 ? null : await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
  return data;
}
function notice(message, error=false) { const el=$('notice'); el.textContent=message; el.style.background=error?'#8c3d34':'#173f30'; el.classList.remove('hidden'); setTimeout(()=>el.classList.add('hidden'),4200); }
function updateAccountUI() {
  $('user-label').textContent = user ? user.name : 'Guest';
  $('auth-name').classList.toggle('hidden', !registerMode);
  $('auth-submit').textContent = registerMode ? 'Create account' : 'Sign in';
  $('register-mode').textContent = registerMode ? 'Back to sign in' : 'Create account';
  $('logout-btn').classList.toggle('hidden', !token);
  $('auth-submit').classList.toggle('hidden', !!token);
  $('register-mode').classList.toggle('hidden', !!token);
  $('auth-name').required = registerMode;
}
$('register-mode').addEventListener('click',()=>{registerMode=!registerMode;updateAccountUI();});
$('logout-btn').addEventListener('click',()=>{token='';user=null;localStorage.removeItem('orderflow_token');localStorage.removeItem('orderflow_user');updateAccountUI();loadCart();loadOrders();notice('Signed out.');});
$('auth-form').addEventListener('submit',async (event)=>{event.preventDefault();try{const payload={email:$('auth-email').value,password:$('auth-password').value};const result=await api(registerMode?'/auth/register':'/auth/login',{method:'POST',body:JSON.stringify(registerMode?{...payload,name:$('auth-name').value}:payload),headers:{}});token=result.access_token;user=result.user;localStorage.setItem('orderflow_token',token);localStorage.setItem('orderflow_user',JSON.stringify(user));registerMode=false;updateAccountUI();notice(`Welcome, ${user.name}.`);await Promise.all([loadCart(),loadOrders()]);}catch(e){notice(e.message,true);}});
async function loadProducts() {const q=encodeURIComponent($('search').value.trim());try{const products=await api(`/products${q?`?q=${q}`:''}`);$('products').innerHTML=products.length?products.map(p=>`<article class="product-card"><div class="product-art">${p.image_url?`<img src="${p.image_url}" alt="${escapeHtml(p.name)}">`:escapeHtml(p.name.slice(0,1).toUpperCase())}</div><div class="product-body"><div class="product-meta"><span>${escapeHtml(p.category)}</span><span>${p.stock>0?`${p.stock} in stock`:'Out of stock'}</span></div><h3>${escapeHtml(p.name)}</h3><p>${escapeHtml(p.description||'A featured OrderFlow product.')}</p><div class="product-foot"><span class="price">${money(p.price)}</span><button class="small-btn" ${p.stock<1?'disabled':''} onclick="addToCart(${p.id})">Add to cart</button></div></div></article>`).join(''):'<div class="loading">No products found. Run the seed script to add demo products.</div>';}catch(e){$('products').innerHTML=`<div class="loading">${escapeHtml(e.message)}</div>`;}}
function escapeHtml(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
async function addToCart(productId){if(!token){notice('Please sign in before adding items.',true);location.hash='#account';return;}try{await api('/cart/items',{method:'POST',body:JSON.stringify({product_id:productId,quantity:1})});notice('Added to your cart.');await loadCart();}catch(e){notice(e.message,true);}}
async function loadCart(){if(!token){$('cart-items').innerHTML='<p class="muted">Sign in to view your cart.</p>';$('subtotal').textContent=money(0);$('total').textContent=money(0);$('cart-count').textContent='0';$('checkout-btn').disabled=true;return;}try{const cart=await api('/cart');$('cart-count').textContent=cart.items.reduce((a,i)=>a+i.quantity,0);$('subtotal').textContent=money(cart.subtotal);$('total').textContent=money(cart.subtotal);$('checkout-btn').disabled=!cart.items.length;$('cart-items').innerHTML=cart.items.length?cart.items.map(i=>`<div class="cart-line"><div><h4>${escapeHtml(i.product_name)}</h4><small>${money(i.unit_price)} each · ${i.available_stock} available</small></div><input type="number" min="1" max="${Math.max(1,i.available_stock)}" value="${i.quantity}" aria-label="Quantity" onchange="updateCartItem(${i.id},this.value)"><strong>${money(i.line_total)}</strong><button class="remove" onclick="removeCartItem(${i.id})">Remove</button></div>`).join(''):'<p class="muted">Your cart is empty. Explore the catalogue to add a product.</p>';}catch(e){notice(e.message,true);}}
async function updateCartItem(id,quantity){try{await api(`/cart/items/${id}`,{method:'PATCH',body:JSON.stringify({quantity:Number(quantity)})});await loadCart();}catch(e){notice(e.message,true);}}
async function removeCartItem(id){try{await api(`/cart/items/${id}`,{method:'DELETE'});await loadCart();}catch(e){notice(e.message,true);}}
$('checkout-btn').addEventListener('click',async()=>{if(!token){notice('Sign in first.',true);return;}const shipping_address={full_name:prompt('Full name for delivery?')||'',line1:prompt('Delivery address (line 1)?')||'',city:prompt('City?')||'',state:prompt('State?')||'',postal_code:prompt('Postal code?')||'',country:'India',phone:prompt('Phone number?')||''};if(Object.values(shipping_address).some(v=>!v)){notice('Checkout cancelled: all delivery fields are required.',true);return;}try{const order=await api('/orders/checkout',{method:'POST',headers:{'Idempotency-Key':crypto.randomUUID()},body:JSON.stringify({shipping_address})});const payment=await api(`/orders/${order.id}/payments`,{method:'POST'});if(payment.provider==='mock'){await api(`/payments/${payment.id}/simulate`,{method:'POST',body:JSON.stringify({success:true})});notice(`Order #${order.id} paid successfully in demo mode.`);}else{notice('Payment created. Complete it using the configured gateway checkout flow.');}await Promise.all([loadCart(),loadOrders(),loadProducts()]);}catch(e){notice(e.message,true);}});
async function loadOrders(){if(!token){$('order-list').innerHTML='<p class="muted">Sign in to see your orders.</p>';return;}try{const orders=await api('/orders/mine');$('order-list').innerHTML=orders.length?orders.map(o=>`<div class="order-row"><div><strong>Order #${o.id}</strong><small>${new Date(o.created_at).toLocaleString()} · ${o.items.length} item(s)</small></div><div style="text-align:right"><span class="pill">${escapeHtml(o.status.replaceAll('_',' '))}</span><small>${money(o.total)}</small></div></div>`).join(''):'<p class="muted">No orders yet.</p>';}catch(e){notice(e.message,true);}}
$('search-btn').addEventListener('click',loadProducts);$('search').addEventListener('keydown',e=>{if(e.key==='Enter')loadProducts();});$('refresh-cart').addEventListener('click',loadCart);$('refresh-orders').addEventListener('click',loadOrders);
updateAccountUI();loadProducts();loadCart();loadOrders();
