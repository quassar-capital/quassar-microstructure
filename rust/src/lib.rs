
//! Deterministic event-time kernels. Research software; not a trading engine.
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use rand::Rng;
use rand::SeedableRng;
use rand_chacha::ChaCha8Rng;

fn check_hawkes(mu: &[f64], alpha: &[Vec<f64>], beta: f64) -> Result<(), String> {
    let n = mu.len();
    if n == 0 || !beta.is_finite() || beta <= 0.0 || mu.iter().any(|x| !x.is_finite() || *x <= 0.0) {
        return Err("baseline intensities and decay must be finite and strictly positive".into());
    }
    if alpha.len() != n || alpha.iter().any(|r| r.len() != n || r.iter().any(|x| !x.is_finite() || *x < 0.0)) {
        return Err("excitation matrix must be square, finite, and nonnegative".into());
    }
    Ok(())
}

/// Excitation from source j to target i is alpha[i][j] * exp(-beta * age).
#[pyfunction]
fn hawkes_intensity(mu: Vec<f64>, alpha: Vec<Vec<f64>>, beta: f64,
                    history: Vec<(f64, usize)>, t: f64) -> PyResult<Vec<f64>> {
    check_hawkes(&mu, &alpha, beta).map_err(PyValueError::new_err)?;
    if !t.is_finite() || t < 0.0 { return Err(PyValueError::new_err("invalid evaluation time")); }
    let mut lambda = mu.clone();
    let mut previous = 0.0;
    for (time, source) in history {
        if !time.is_finite() || time < previous || time > t || source >= mu.len() {
            return Err(PyValueError::new_err("history must be ordered and within evaluation horizon"));
        }
        for i in 0..mu.len() { lambda[i] += alpha[i][source] * (-beta * (t-time)).exp(); }
        previous = time;
    }
    Ok(lambda)
}

/// Ogata thinning with an exact decaying upper envelope between accepted events.
/// Returns time/type tuples; maximum event count is a hard computational safeguard.
#[pyfunction]
fn simulate_hawkes(mu: Vec<f64>, alpha: Vec<Vec<f64>>, beta: f64,
                   horizon: f64, seed: u64, max_events: usize) -> PyResult<Vec<(f64, usize)>> {
    check_hawkes(&mu, &alpha, beta).map_err(PyValueError::new_err)?;
    if !horizon.is_finite() || horizon <= 0.0 || max_events == 0 {
        return Err(PyValueError::new_err("horizon and max_events must be positive"));
    }
    let mut rng = ChaCha8Rng::seed_from_u64(seed);
    let n = mu.len();
    let mut excitation = vec![0.0; n];
    let mut out = Vec::new();
    let mut t = 0.0;
    loop {
        let bound: f64 = mu.iter().zip(&excitation).map(|(a,b)| a+b).sum();
        let u: f64 = rng.gen::<f64>().max(f64::MIN_POSITIVE);
        let dt = -u.ln() / bound;
        if !dt.is_finite() || t + dt >= horizon { break; }
        t += dt;
        let decay = (-beta * dt).exp();
        for x in &mut excitation { *x *= decay; }
        let total: f64 = mu.iter().zip(&excitation).map(|(a,b)| a+b).sum();
        if rng.gen::<f64>() * bound >= total { continue; }
        let mut draw = rng.gen::<f64>() * total;
        let mut kind = n - 1;
        for i in 0..n {
            draw -= mu[i] + excitation[i];
            if draw < 0.0 { kind = i; break; }
        }
        if out.len() >= max_events { return Err(PyValueError::new_err("event budget exhausted")); }
        out.push((t, kind));
        for i in 0..n { excitation[i] += alpha[i][kind]; }
    }
    Ok(out)
}

/// Simple price-time FIFO limit book. Prices use integer ticks, sizes integer lots.
#[derive(Clone, Debug)]
struct Order { id: u64, price: i64, remaining: u64, sequence: u64 }

#[pyclass]
struct LimitBook { bids: Vec<Order>, asks: Vec<Order>, sequence: u64 }

#[pymethods]
impl LimitBook {
    #[new]
    fn new() -> Self { Self { bids: vec![], asks: vec![], sequence: 0 } }
    fn submit(&mut self, id: u64, side: &str, price: i64, quantity: u64) -> PyResult<Vec<(u64,u64,i64,u64)>> {
        if price <= 0 || quantity == 0 || self.bids.iter().chain(&self.asks).any(|o| o.id == id) {
            return Err(PyValueError::new_err("invalid order or duplicate active id"));
        }
        if side != "buy" && side != "sell" { return Err(PyValueError::new_err("side must be buy or sell")); }
        let mut left = quantity;
        let mut trades = Vec::new();
        let opposing = if side == "buy" { &mut self.asks } else { &mut self.bids };
        opposing.sort_by_key(|o| if side == "buy" { (o.price, o.sequence) } else { (-o.price, o.sequence) });
        while left > 0 && !opposing.is_empty() {
            let crossed = if side == "buy" { opposing[0].price <= price } else { opposing[0].price >= price };
            if !crossed { break; }
            let qty = left.min(opposing[0].remaining);
            trades.push((id, opposing[0].id, opposing[0].price, qty));
            left -= qty;
            opposing[0].remaining -= qty;
            if opposing[0].remaining == 0 { opposing.remove(0); }
        }
        if left > 0 {
            self.sequence = self.sequence.checked_add(1).ok_or_else(|| PyValueError::new_err("sequence overflow"))?;
            let order = Order { id, price, remaining: left, sequence: self.sequence };
            if side == "buy" { self.bids.push(order); } else { self.asks.push(order); }
        }
        Ok(trades)
    }
    fn cancel(&mut self, id: u64) -> bool {
        for book in [&mut self.bids, &mut self.asks] {
            if let Some(i) = book.iter().position(|o| o.id == id) { book.remove(i); return true; }
        }
        false
    }
    fn best_bid(&self) -> Option<i64> { self.bids.iter().map(|o| o.price).max() }
    fn best_ask(&self) -> Option<i64> { self.asks.iter().map(|o| o.price).min() }
    fn total_volume(&self) -> u64 { self.bids.iter().chain(&self.asks).map(|o| o.remaining).sum() }
}

#[pymodule]
fn _core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(hawkes_intensity, m)?)?;
    m.add_function(wrap_pyfunction!(simulate_hawkes, m)?)?;
    m.add_class::<LimitBook>()?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn no_excitation_is_baseline() {
        let out = hawkes_intensity(vec![2.0], vec![vec![0.0]], 1.0, vec![(0.5,0)], 1.0).unwrap();
        assert_eq!(out, vec![2.0]);
    }
    #[test]
    fn fifo_at_same_price() {
        let mut book = LimitBook::new();
        book.submit(1,"sell",100,2).unwrap();
        book.submit(2,"sell",100,3).unwrap();
        let trades = book.submit(3,"buy",100,4).unwrap();
        assert_eq!(trades, vec![(3,1,100,2),(3,2,100,2)]);
        assert_eq!(book.best_ask(), Some(100));
        assert_eq!(book.total_volume(), 1);
    }
}
