from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import Perfume
from .forms import PerfumeForm

def perfume_list(request):
    perfumes = Perfume.objects.all()
    return render(request, 'rubiPerfumeria/perfume_list.html', {'perfumes': perfumes})

def perfume_detail(request, pk):
    perfume = get_object_or_404(Perfume, pk=pk)
    return render(request, 'rubiPerfumeria/perfume_detail.html', {'perfume': perfume})

def perfume_create(request):
    if request.method == 'POST':
        form = PerfumeForm(request.POST, request.FILES)
        if form.is_valid():
            perfume = form.save()
            messages.success(request, f'Perfume "{perfume.nombre}" creado exitosamente.')
            return redirect('perfume_detail', pk=perfume.pk)
    else:
        form = PerfumeForm()
    return render(request, 'rubiPerfumeria/perfume_form.html', {'form': form, 'action': 'Crear'})

def perfume_update(request, pk):
    perfume = get_object_or_404(Perfume, pk=pk)
    if request.method == 'POST':
        form = PerfumeForm(request.POST, request.FILES, instance=perfume)
        if form.is_valid():
            perfume = form.save()
            messages.success(request, f'Perfume "{perfume.nombre}" actualizado exitosamente.')
            return redirect('perfume_detail', pk=perfume.pk)
    else:
        form = PerfumeForm(instance=perfume)
    return render(request, 'rubiPerfumeria/perfume_form.html', {'form': form, 'action': 'Actualizar', 'perfume': perfume})

def perfume_delete(request, pk):
    perfume = get_object_or_404(Perfume, pk=pk)
    if request.method == 'POST':
        nombre = perfume.nombre
        perfume.delete()
        messages.success(request, f'Perfume "{nombre}" eliminado exitosamente.')
        return redirect('perfume_list')
    return render(request, 'rubiPerfumeria/perfume_confirm_delete.html', {'perfume': perfume})
