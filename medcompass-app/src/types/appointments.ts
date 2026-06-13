export interface Department {
  id: number;
  name: string;
}

export interface Doctor {
  id: number;
  full_name: string;
  department_id: number;
}

export interface AppointmentSlot {
  id: number;
  department: Department;
  doctor: Doctor;
  start_time: string; // ISO
  status: string;
}

export interface BookedAppointment extends AppointmentSlot {
  patientName?: string;
  appointmentNumber?: string;
}
