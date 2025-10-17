"""
Wave physics: refraction, shoaling, and transformation

Implements shallow-water wave physics:
- Wave speed as function of depth: c = √(g·h) for h << λ
- Snell's law for refraction
- Shoaling coefficient for height transformation
"""

import numpy as np
from typing import Tuple
import logging

logger = logging.getLogger(__name__)

# Constants
GRAVITY = 9.81  # m/s²
DEEP_WATER_THRESHOLD = 0.5  # h/λ ratio for deep water


def wave_speed(depth: float, period: float, deep_water: bool = False) -> float:
    """
    Calculate wave celerity (speed)

    Args:
        depth: Water depth in meters (positive)
        period: Wave period in seconds
        deep_water: If True, use deep water approximation

    Returns:
        Wave speed in m/s
    """
    if deep_water or depth < 0:
        # Deep water: c = gT / (2π)
        return (GRAVITY * period) / (2 * np.pi)

    # Shallow water approximation: c ≈ √(g·h)
    # Valid when h < λ/20
    wavelength = (GRAVITY * period**2) / (2 * np.pi)

    if depth / wavelength < 0.05:
        # Shallow water
        return np.sqrt(GRAVITY * depth)
    else:
        # Intermediate depth - use dispersion relation
        # c = √(gλ/2π * tanh(2πh/λ))
        # Iterative solution needed, use shallow water as approximation
        return np.sqrt(GRAVITY * depth * np.tanh(2 * np.pi * depth / wavelength))


def shoaling_coefficient(h_deep: float, h_shallow: float, period: float) -> float:
    """
    Calculate shoaling coefficient (wave height amplification)

    K_s = √(c_deep / c_shallow) for energy conservation
    H_shallow = K_s * H_deep

    Args:
        h_deep: Deep water depth (m)
        h_shallow: Shallow water depth (m)
        period: Wave period (s)

    Returns:
        Shoaling coefficient K_s
    """
    c_deep = wave_speed(h_deep, period, deep_water=True)
    c_shallow = wave_speed(h_shallow, period, deep_water=False)

    if c_shallow > 0:
        K_s = np.sqrt(c_deep / c_shallow)
    else:
        K_s = 1.0

    # Limit to reasonable range (breaking waves)
    K_s = np.clip(K_s, 0.5, 3.0)

    return K_s


def refract_wave_angle(
    angle_deep: float, h_deep: float, h_shallow: float, period: float
) -> float:
    """
    Apply Snell's law to refract wave direction

    sin(θ_shallow) / c_shallow = sin(θ_deep) / c_deep

    Args:
        angle_deep: Deep water wave angle (degrees, from shore normal)
        h_deep: Deep water depth (m)
        h_shallow: Shallow water depth (m)
        period: Wave period (s)

    Returns:
        Refracted angle in degrees (from shore normal)
    """
    c_deep = wave_speed(h_deep, period, deep_water=True)
    c_shallow = wave_speed(h_shallow, period, deep_water=False)

    angle_deep_rad = np.radians(angle_deep)

    # Snell's law
    sin_shallow = (c_shallow / c_deep) * np.sin(angle_deep_rad)

    # Clip to valid range
    sin_shallow = np.clip(sin_shallow, -1.0, 1.0)

    angle_shallow_rad = np.arcsin(sin_shallow)
    angle_shallow = np.degrees(angle_shallow_rad)

    return angle_shallow


def compute_wave_transformation(
    Hs_deep: float,
    Tp: float,
    dir_deep: float,
    shore_normal: float,
    depths: np.ndarray,
) -> Tuple[float, float, float]:
    """
    Transform wave from deep to shallow water

    Args:
        Hs_deep: Deep water significant wave height (m)
        Tp: Peak wave period (s)
        dir_deep: Deep water wave direction (degrees, oceanographic)
        shore_normal: Shore normal direction (degrees)
        depths: Array of depths along transect from deep to shore (m, positive)

    Returns:
        (Hs_nearshore, dir_nearshore, refraction_coeff) tuple
    """
    # Angle between wave direction and shore normal
    # Wave comes FROM dir_deep, shore normal points TO sea
    incident_angle = (dir_deep - shore_normal + 180) % 360

    # Normalize to -180 to 180
    if incident_angle > 180:
        incident_angle -= 360

    # Start from deep water
    H_current = Hs_deep
    angle_current = incident_angle
    refraction_coeff = 1.0

    # Step through depths
    for i in range(len(depths) - 1):
        h1 = depths[i]
        h2 = depths[i + 1]

        if h2 <= 0:
            break

        # Refraction
        angle_new = refract_wave_angle(angle_current, h1, h2, Tp)

        # Refraction coefficient (for amplitude)
        if abs(angle_current) > 0.1:
            K_r = np.sqrt(np.cos(np.radians(angle_current)) / np.cos(np.radians(angle_new)))
        else:
            K_r = 1.0

        # Shoaling
        K_s = shoaling_coefficient(h1, h2, Tp)

        # Update height and angle
        H_current = H_current * K_s * K_r
        angle_current = angle_new
        refraction_coeff *= K_r

    # Convert back to oceanographic direction
    dir_nearshore = (shore_normal - angle_current - 180) % 360

    return H_current, dir_nearshore, refraction_coeff


def calculate_exposure(wave_dir: float, shore_normal: float) -> float:
    """
    Calculate exposure factor (0-1) based on wave approach angle

    Exposure = cos(incident_angle)^γ, clipped to [0, 1]

    Args:
        wave_dir: Wave direction (degrees, oceanographic - direction FROM)
        shore_normal: Shore normal direction (degrees - pointing TO sea)

    Returns:
        Exposure factor (0 = fully shadowed, 1 = directly exposed)
    """
    # Incident angle
    incident_angle = (wave_dir - shore_normal + 180) % 360

    # Normalize to -180 to 180
    if incident_angle > 180:
        incident_angle -= 360

    # Exposure (clamp negative to 0)
    exposure = max(0, np.cos(np.radians(incident_angle)))

    # Apply exponent for sharper falloff (γ = 1.2 from PRD)
    gamma = 1.2
    exposure = exposure**gamma

    return exposure


def breaking_depth(Hs: float, slope: float = 0.05) -> float:
    """
    Estimate breaking depth using wave height

    H_break / h_break ≈ 0.78 (standard breaker index)

    Args:
        Hs: Significant wave height (m)
        slope: Bottom slope (default 0.05)

    Returns:
        Breaking depth (m, positive)
    """
    # Breaker index (depends on slope)
    gamma_break = 0.78 + 0.2 * slope

    h_break = Hs / gamma_break

    return h_break
