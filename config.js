/* Mastara ordering — everything you are likely to change lives here.
   Plain <script>, no build step. Edit, save, refresh.                        */

const CONFIG = {
  /* ---------------------------------------------------------------- money */
  currency: "PKR",
  currencySymbol: "Rs",

  // Percentages added on top of the subtotal. Both 0 = totals are just the food.
  // Set these only to what Mastara actually charges — they print on the guest's ticket.
  taxPercent: 0,
  servicePercent: 0,

  /* ---------------------------------------------------------------- tables */
  tableCount: 24,          // how many table QR codes qr.html prints
  requireTable: true,      // an order cannot be sent without a table number

  /* ------------------------------------------------------------- ordering */
  // Guests can send an order to the kitchen. Turn off to make the site a
  // browse-only 3D menu again.
  orderingEnabled: true,

  // Largest quantity of one dish a guest can add without talking to a waiter.
  maxQtyPerItem: 20,

  /* ------------------------------------------------ where orders are sent */
  // THIS IS THE PLUG. Until an endpoint is set, orders are saved on the device
  // and the guest gets a WhatsApp button that opens a formatted ticket addressed
  // to the restaurant. Fill `url` in and every order POSTs there as JSON
  // (see docs/order-payload.md for the exact shape) with no other change.
  orderEndpoint: {
    url: "/orders",                // e.g. "https://api.mastara.com/orders"
    method: "POST",
    headers: {},                   // e.g. { "Authorization": "Bearer …" }
    timeoutMs: 8000,
  },

  // Fallback + belt-and-braces channel. The guest taps it; nothing is sent
  // automatically on their behalf.
  whatsappFallback: true,

  /* ------------------------------------------------------------- kitchen */
  // kitchen.html polls this for live orders. Leave empty and it shows the
  // orders placed on this device (enough to demo the whole flow).
  kitchenFeedUrl: "/orders",
  kitchenPollMs: 15000,
};
