from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from .models import Perfume
from .forms import PerfumeForm


def perfume_list(request):
    perfumes = Perfume.objects.all()
    return render(request, 'perfumes/perfume_list.html', {'perfumes': perfumes})


def perfume_detail(request, pk):
    perfume = get_object_or_404(Perfume, pk=pk)
    return render(request, 'perfumes/perfume_detail.html', {'perfume': perfume})


def perfume_create(request):
    if request.method == 'POST':
        form = PerfumeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Perfume creado exitosamente.')
            return redirect('perfume_list')
    else:
        form = PerfumeForm()
    return render(request, 'perfumes/perfume_form.html', {'form': form, 'action': 'Crear'})


def perfume_update(request, pk):
    perfume = get_object_or_404(Perfume, pk=pk)
    if request.method == 'POST':
        form = PerfumeForm(request.POST, instance=perfume)
        if form.is_valid():
            form.save()
            messages.success(request, 'Perfume actualizado exitosamente.')
            return redirect('perfume_detail', pk=pk)
    else:
        form = PerfumeForm(instance=perfume)
    return render(request, 'perfumes/perfume_form.html', {'form': form, 'action': 'Editar', 'perfume': perfume})


def perfume_delete(request, pk):
    perfume = get_object_or_404(Perfume, pk=pk)
    if request.method == 'POST':
        perfume.delete()
        messages.success(request, 'Perfume eliminado exitosamente.')
        return redirect('perfume_list')
    return render(request, 'perfumes/perfume_confirm_delete.html', {'perfume': perfume})
