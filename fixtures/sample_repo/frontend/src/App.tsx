import { useEffect, useState } from "react";
import "./App.css";
import {
  createReservation,
  deleteReservation,
  listReservations,
  updateStatus,
  type Reservation,
  type ReservationStatus,
} from "./api";

const emptyForm = { guest_name: "", property_id: "", check_in: "", check_out: "" };

function App() {
  const [reservations, setReservations] = useState<Reservation[]>([]);
  const [form, setForm] = useState(emptyForm);
  const [error, setError] = useState<string | null>(null);

  function refresh() {
    listReservations()
      .then(setReservations)
      .catch((err: Error) => setError(err.message));
  }

  useEffect(refresh, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    try {
      await createReservation({
        ...form,
        check_in: new Date(form.check_in).toISOString(),
        check_out: new Date(form.check_out).toISOString(),
      });
      setForm(emptyForm);
      refresh();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function handleStatusChange(id: number, status: ReservationStatus) {
    await updateStatus(id, status);
    refresh();
  }

  async function handleDelete(id: number) {
    await deleteReservation(id);
    refresh();
  }

  return (
    <main>
      <h1>Reservations</h1>
      {error && <p role="alert">{error}</p>}

      <form onSubmit={handleSubmit}>
        <input
          placeholder="Guest name"
          value={form.guest_name}
          onChange={(e) => setForm({ ...form, guest_name: e.target.value })}
          required
        />
        <input
          placeholder="Property ID"
          value={form.property_id}
          onChange={(e) => setForm({ ...form, property_id: e.target.value })}
          required
        />
        <input
          type="datetime-local"
          value={form.check_in}
          onChange={(e) => setForm({ ...form, check_in: e.target.value })}
          required
        />
        <input
          type="datetime-local"
          value={form.check_out}
          onChange={(e) => setForm({ ...form, check_out: e.target.value })}
          required
        />
        <button type="submit">Create reservation</button>
      </form>

      <table>
        <thead>
          <tr>
            <th>Guest</th>
            <th>Property</th>
            <th>Check-in</th>
            <th>Check-out</th>
            <th>Status</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {reservations.map((r) => (
            <tr key={r.id}>
              <td>{r.guest_name}</td>
              <td>{r.property_id}</td>
              <td>{new Date(r.check_in).toLocaleString()}</td>
              <td>{new Date(r.check_out).toLocaleString()}</td>
              <td>
                <select
                  value={r.status}
                  onChange={(e) =>
                    handleStatusChange(r.id, e.target.value as ReservationStatus)
                  }
                >
                  <option value="pending">pending</option>
                  <option value="confirmed">confirmed</option>
                  <option value="cancelled">cancelled</option>
                </select>
              </td>
              <td>
                <button onClick={() => handleDelete(r.id)}>Delete</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </main>
  );
}

export default App;
