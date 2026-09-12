const API_BASE_URL = "http://localhost:8000";

export type ReservationStatus = "pending" | "confirmed" | "cancelled";

export type Reservation = {
  id: number;
  guest_name: string;
  property_id: string;
  check_in: string;
  check_out: string;
  status: ReservationStatus;
  created_at: string;
};

export type NewReservation = {
  guest_name: string;
  property_id: string;
  check_in: string;
  check_out: string;
};

export async function listReservations(): Promise<Reservation[]> {
  const res = await fetch(`${API_BASE_URL}/reservations`);
  if (!res.ok) throw new Error(`Failed to load reservations (${res.status})`);
  return res.json();
}

export async function createReservation(data: NewReservation): Promise<Reservation> {
  const res = await fetch(`${API_BASE_URL}/reservations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(`Failed to create reservation (${res.status})`);
  return res.json();
}

export async function updateStatus(id: number, status: ReservationStatus): Promise<Reservation> {
  const res = await fetch(`${API_BASE_URL}/reservations/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
  if (!res.ok) throw new Error(`Failed to update reservation (${res.status})`);
  return res.json();
}

export async function deleteReservation(id: number): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/reservations/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`Failed to delete reservation (${res.status})`);
}
